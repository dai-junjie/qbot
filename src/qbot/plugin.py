from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import re
from time import monotonic
import unicodedata
from zoneinfo import ZoneInfo

from nonebot import get_driver, logger, on, on_message
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, MessageSegment
from nonebot.exception import ActionFailed
from nonebot.plugin import require

from qbot.config import settings
from qbot.collector import get_group_members
from qbot.ranker import rank_and_percentile
from qbot.repository import ScoreRepository
from qbot.service import ScoreStatService
from qbot.setops import (
    build_overlap_text,
    collect_candidates,
    is_zheji_candidate,
    is_zheruan_candidate,
    member_profile_text,
    parse_zheji_score,
    parse_zheruan_score,
)

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


driver = get_driver()
repo = ScoreRepository(settings.db_path)
service = ScoreStatService(
    repository=repo,
    history_window_hours=settings.history_window_hours,
    retention_days=settings.retention_days,
    font_path=settings.font_path,
)

_locks: dict[int, asyncio.Lock] = {}
_last_manual_trigger_at: dict[int, float] = {}
MANUAL_TRIGGER_COOLDOWN_SECONDS = 8.0
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _get_lock(group_id: int) -> asyncio.Lock:
    if group_id not in _locks:
        _locks[group_id] = asyncio.Lock()
    return _locks[group_id]


def _image_segment_from_file(path: Path) -> MessageSegment:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return MessageSegment.image(f"base64://{b64}")


def _is_group_allowed(group_id: int) -> bool:
    return str(group_id) in set(settings.enabled_groups)


def _normalize_usage_command(command: str) -> str:
    if command == "scorestat":
        return "stat"
    return command


async def _send_stat(bot: Bot, group_id: int) -> bool:
    lock = _get_lock(group_id)
    async with lock:
        logger.info("Start scorestat for group {}", group_id)
        result = None
        for attempt in range(3):
            try:
                result = await service.run_once(bot, group_id)
                break
            except Exception:
                logger.exception(
                    "Group {} stat compute attempt {} failed",
                    group_id,
                    attempt + 1,
                )

        if result is None:
            logger.error("Group {} stat failed after retries", group_id)
            return False

        try:
            await bot.send_group_msg(group_id=group_id, message=result.summary_text)
        except ActionFailed as exc:
            logger.warning("Group {} summary send failed: {}", group_id, exc)
            return False

        if result.bucket_image:
            try:
                await bot.send_group_msg(
                    group_id=group_id,
                    message=_image_segment_from_file(result.bucket_image.resolve()),
                )
            except ActionFailed as exc:
                logger.warning("Group {} bucket image send failed: {}", group_id, exc)

        if result.trend_image:
            try:
                await bot.send_group_msg(
                    group_id=group_id,
                    message=_image_segment_from_file(result.trend_image.resolve()),
                )
            except ActionFailed as exc:
                logger.warning("Group {} trend image send failed: {}", group_id, exc)

        return True


scorestat_msg = on_message(priority=10, block=True)
scorestat_sent_msg = on("message_sent", priority=10, block=False)

STAT_HELP_TEXT = (
    "规则：\n"
    "1) 仅统计群名片/昵称中 `分数-名字` 或 `分数—名字`\n"
    "2) 分数范围 350-500\n"
    "3) 5 分一档，从 350 起\n"
    "4) 档位上限 min(500, 最高分+5)"
)

RANK_HELP_TEXT = (
    "用法：`/rank` 或 `/rank win`\n"
    "功能：`/rank` 查询你自己的排名、百分位、是否在复试线上；`/rank win` 额外显示 202 线/202均分机考追分分析。\n"
    "前提：你的名片/昵称必须是 `分数-名字` 或 `分数—名字`，且分数在 350-500。"
)

RANK_COMP_HELP_TEXT = (
    "用法：`/rank-comp`\n"
    "功能：查询你在浙软与浙计两边的个人排名。\n"
    "规则：\n"
    "1) 浙软按 `分数-名字` 或 `分数—名字`\n"
    "2) 浙计按 `26-专业-分数-名字`（默认用你在浙软的分数换算位次）\n"
    "3) 分数范围 350-500"
)

SET_HELP_TEXT = (
    "用法：`/set`\n"
    "功能：对比浙软群(当前群)与浙计群的考生名单，按 QQ 检测重合。\n"
    "筛选规则：\n"
    "1) 浙软群：`分数-名字` 或 `分数—名字`，分数 350-500\n"
    "2) 浙计群：`26-专业-分数-名字`，分数 350-500"
)

ALL_HELP_TEXT = (
    "可用命令：\n"
    "`/h`：查看本帮助\n"
    "`/stat`：统计当前群分数分布（兼容 `/scorestat`）\n"
    "`/stat help`：查看统计规则\n"
    "`/rank`：查询你在浙软群的排名\n"
    "`/rank win`：在个人排名后附加机考追分分析\n"
    "`/rank help`：查看个人排名规则\n"
    "`/rank-comp`：查询跨群排名对比\n"
    "`/rank-comp help`：查看跨群排名规则\n"
    "`/set`：查询浙软与浙计考生 QQ 重合\n"
    "`/set help`：查看重合检测规则"
)


@driver.on_startup
async def _on_startup() -> None:
    await repo.init()
    logger.info("qbot repository initialized at {}", settings.db_path)
    logger.info("qbot enabled groups: {}", settings.enabled_groups)

    @scheduler.scheduled_job(
        "cron",
        minute="0",
        hour="8-23/2",
        timezone=BEIJING_TZ,
        id="qbot_scorestat",
    )
    async def _scheduled_stat() -> None:
        if not settings.enabled_groups:
            return
        bots = list(get_driver().bots.values())
        if not bots:
            logger.warning("No active bot found for scheduled scorestat")
            return
        bot = bots[0]
        for group_id_raw in settings.enabled_groups:
            try:
                group_id = int(group_id_raw)
            except ValueError:
                logger.warning("Skip invalid group id in QBOT_ENABLED_GROUPS: {}", group_id_raw)
                continue
            await _send_stat(bot, group_id)


@scorestat_msg.handle()
async def _handle_scorestat(bot: Bot, event: GroupMessageEvent) -> None:
    allowed = _is_group_allowed(event.group_id)
    if not allowed:
        logger.info(
            "Whitelist check: group_id={} allowed={}",
            event.group_id,
            allowed,
        )
        return

    raw_text = event.get_plaintext().strip()
    parsed = _parse_bot_command(raw_text)
    if parsed is None:
        return
    command, action = parsed

    logger.info(
        "Received command {} {} from user {} in group {}",
        command,
        action,
        event.user_id,
        event.group_id,
    )
    await _handle_command(
        bot=bot,
        group_id=event.group_id,
        user_id=event.user_id,
        command=command,
        action=action,
        matcher=scorestat_msg,
    )
    logger.info("Whitelist check: group_id={} allowed={}", event.group_id, allowed)


def _extract_plain_text_from_message_payload(message: object) -> str:
    if isinstance(message, str):
        return message.strip()
    if isinstance(message, list):
        parts: list[str] = []
        for seg in message:
            if not isinstance(seg, dict):
                continue
            if seg.get("type") != "text":
                continue
            data = seg.get("data")
            if isinstance(data, dict):
                text = data.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def _parse_bot_command(raw_text: str) -> tuple[str, str] | None:
    # Normalize full-width forms and strip invisible separators to improve
    # command recognition from different clients/input methods.
    normalized = unicodedata.normalize("NFKC", raw_text)
    normalized = (
        normalized.replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
        .strip()
        .lower()
    )
    command_re = re.compile(
        r"^/?\s*(stat|scorestat|rank-comp|rank|set|h)(?:\s+(help|win))?\s*$"
    )
    m = command_re.match(normalized)
    if m:
        command = m.group(1)
        action_token = m.group(2)
        if action_token == "win" and command != "rank":
            return None
        action = action_token if action_token else "run"
        return (command, action)
    if normalized.startswith("/") or normalized.startswith("／"):
        logger.info("Unrecognized slash command raw={!r} normalized={!r}", raw_text, normalized)
    return None


async def _send_text(bot: Bot, group_id: int, text: str, matcher=None) -> None:
    if matcher is not None:
        await matcher.finish(text)
    await bot.send_group_msg(group_id=group_id, message=text)


async def _handle_command(
    bot: Bot,
    group_id: int,
    user_id: int,
    command: str,
    action: str,
    matcher=None,
) -> None:
    try:
        await repo.log_command_usage(
            group_id=group_id,
            user_id=user_id,
            command=_normalize_usage_command(command),
            action=action,
        )
    except Exception:
        logger.exception(
            "Command usage log failed: group_id={} user_id={} command={} action={}",
            group_id,
            user_id,
            command,
            action,
        )

    if command in {"stat", "scorestat"}:
        if action == "help":
            await _send_text(bot, group_id, STAT_HELP_TEXT, matcher=matcher)
            return
        await _run_scorestat_with_cooldown(bot, group_id, matcher)
        return

    if command == "h":
        await _send_text(bot, group_id, ALL_HELP_TEXT, matcher=matcher)
        return

    if command == "rank":
        if action == "help":
            await _send_text(bot, group_id, RANK_HELP_TEXT, matcher=matcher)
            return
        rank_result = await service.query_self_rank(
            bot,
            group_id,
            user_id,
            include_comeback=(action == "win"),
        )
        await _send_text(bot, group_id, rank_result.text, matcher=matcher)
        return

    if command == "rank-comp":
        if action == "help":
            await _send_text(bot, group_id, RANK_COMP_HELP_TEXT, matcher=matcher)
            return
        await _run_rank_comp(bot, group_id, user_id, matcher)
        return

    if command == "set":
        if action == "help":
            await _send_text(bot, group_id, SET_HELP_TEXT, matcher=matcher)
            return
        await _run_set_overlap_check(bot, group_id, matcher)
        return


async def _run_scorestat_with_cooldown(bot: Bot, group_id: int, matcher) -> None:
    now = monotonic()
    last = _last_manual_trigger_at.get(group_id, 0.0)
    if now - last < MANUAL_TRIGGER_COOLDOWN_SECONDS:
        await matcher.finish("触发过于频繁，请稍后再试。")

    _last_manual_trigger_at[group_id] = now
    ok = await _send_stat(bot, group_id)
    if not ok:
        await matcher.finish("统计执行失败（可能是群成员接口或图片发送失败），请查看 bot 日志。")


async def _run_set_overlap_check(bot: Bot, group_id: int, matcher) -> None:
    try:
        local_members = await get_group_members(bot, group_id)
        zheji_members = await get_group_members(bot, settings.zheji_group_id)
    except Exception:
        logger.exception("Set overlap check failed to fetch group member list")
        await matcher.finish("名单查询失败，请检查 OneBot 接口和群可见性。")

    local_candidates = collect_candidates(local_members, is_zheruan_candidate)
    zheji_candidates = collect_candidates(zheji_members, is_zheji_candidate)
    result = build_overlap_text(
        local_group_id=group_id,
        zheji_group_id=settings.zheji_group_id,
        local_candidates=local_candidates,
        zheji_candidates=zheji_candidates,
    )
    await _send_text(bot, group_id, result, matcher=matcher)


def _compute_rank_stats(scores: list[int], own_score: int) -> tuple[int, int, int, float]:
    sorted_scores = sorted(scores, reverse=True)
    return rank_and_percentile(sorted_scores, own_score)


def _collect_scores(members: list[dict], score_parser) -> list[int]:
    scores: list[int] = []
    for member in members:
        profile = member_profile_text(member)
        score = score_parser(profile)
        if score is not None:
            scores.append(score)
    return scores


def _extract_local_self_score(local_members: list[dict], user_id: int) -> tuple[int | None, str]:
    self_found = False
    self_profile = ""
    self_score: int | None = None

    for member in local_members:
        uid = member.get("user_id")
        if not isinstance(uid, int) or uid != user_id:
            continue
        self_found = True
        self_profile = member_profile_text(member)
        self_score = parse_zheruan_score(self_profile)
        break

    if not self_found:
        return None, "浙软：未找到你的群成员记录。"
    if self_score is None:
        if not self_profile:
            return None, "浙软：你的名片/昵称为空，无法计算。"
        return None, "浙软：你的名片/昵称不符合格式（分数-名字）。"
    return self_score, ""


async def _run_rank_comp(bot: Bot, group_id: int, user_id: int, matcher) -> None:
    try:
        local_members = list(await get_group_members(bot, group_id))
        zheji_members = list(await get_group_members(bot, settings.zheji_group_id))
    except Exception:
        logger.exception("Rank comp failed to fetch group member list")
        await matcher.finish("查询失败：无法拉取群成员列表，请检查 OneBot 接口。")

    self_score, self_score_error = _extract_local_self_score(local_members, user_id)
    if self_score is None:
        await _send_text(bot, group_id, "\n".join(["=== 跨群个人排名 ===", f"QQ：{user_id}", self_score_error]), matcher=matcher)
        return

    local_scores = _collect_scores(local_members, parse_zheruan_score)
    zheji_scores = _collect_scores(zheji_members, parse_zheji_score)
    if not local_scores:
        await _send_text(bot, group_id, "浙软暂无有效考生样本，无法换算。", matcher=matcher)
        return
    if not zheji_scores:
        await _send_text(bot, group_id, "浙计暂无有效考生样本，无法换算。", matcher=matcher)
        return

    local_best, _, local_tie, local_pct = _compute_rank_stats(local_scores, self_score)
    zheji_best, _, zheji_tie, zheji_pct = _compute_rank_stats(zheji_scores, self_score)

    table_lines = [
        "=== 跨群个人排名 ===",
        "学院 | 分数 | 位次 | 百分位",
        f"浙软 | {self_score} | {local_best}/{len(local_scores)}(同分{local_tie}) | {local_pct:.1f}%",
        f"浙计 | {self_score}* | {zheji_best}/{len(zheji_scores)}(同分{zheji_tie}) | {zheji_pct:.1f}%",
        "* 浙计按浙软同分换算",
    ]
    text = "\n".join(table_lines)
    await _send_text(bot, group_id, text, matcher=matcher)


@scorestat_sent_msg.handle()
async def _handle_scorestat_self_sent(bot: Bot, event: Event) -> None:
    payload = event.model_dump()
    if payload.get("message_type") != "group":
        return
    group_id = payload.get("group_id")
    if not isinstance(group_id, int):
        return
    allowed = _is_group_allowed(group_id)
    if not allowed:
        logger.info(
            "Whitelist check(self_sent): group_id={} allowed={}",
            group_id,
            allowed,
        )
        return

    raw_text = str(payload.get("raw_message") or "").strip()
    if not raw_text:
        raw_text = _extract_plain_text_from_message_payload(payload.get("message"))

    parsed = _parse_bot_command(raw_text)
    if parsed is None:
        return
    command, action = parsed
    user_id = int(payload.get("user_id") or payload.get("self_id") or 0)

    logger.info(
        "Received self-sent command {} {} in group {}",
        command,
        action,
        group_id,
    )
    await _handle_command(
        bot=bot,
        group_id=group_id,
        user_id=user_id,
        command=command,
        action=action,
        matcher=scorestat_sent_msg,
    )
    logger.info("Whitelist check(self_sent): group_id={} allowed={}", group_id, allowed)

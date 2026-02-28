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
from qbot.repository import ScoreRepository
from qbot.service import ScoreStatService

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

SCORESTAT_HELP_TEXT = (
    "规则：\n"
    "1) 仅统计群名片/昵称中 `分数-名字` 或 `分数—名字`\n"
    "2) 分数范围 350-500\n"
    "3) 5 分一档，从 350 起\n"
    "4) 档位上限 min(500, 最高分+5)"
)

RANK_HELP_TEXT = (
    "用法：`/rank`\n"
    "功能：查询你自己的排名、百分位、是否在复试线上。\n"
    "前提：你的名片/昵称必须是 `分数-名字` 或 `分数—名字`，且分数在 350-500。"
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
    command_re = re.compile(r"^/?\s*(scorestat|rank)(?:\s+(help))?\s*$")
    m = command_re.match(normalized)
    if m:
        command = m.group(1)
        action = "help" if m.group(2) else "run"
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
    if command == "scorestat":
        if action == "help":
            await _send_text(bot, group_id, SCORESTAT_HELP_TEXT, matcher=matcher)
            return
        await _run_scorestat_with_cooldown(bot, group_id, matcher)
        return

    if command == "rank":
        if action == "help":
            await _send_text(bot, group_id, RANK_HELP_TEXT, matcher=matcher)
            return
        rank_result = await service.query_self_rank(bot, group_id, user_id)
        await _send_text(bot, group_id, rank_result.text, matcher=matcher)
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

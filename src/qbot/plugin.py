from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from time import monotonic
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


@driver.on_startup
async def _on_startup() -> None:
    await repo.init()
    logger.info("qbot repository initialized at {}", settings.db_path)

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
        for group_id in settings.enabled_groups:
            await _send_stat(bot, group_id)


@scorestat_msg.handle()
async def _handle_scorestat(bot: Bot, event: GroupMessageEvent) -> None:
    raw_text = event.get_plaintext().strip()
    action = _parse_scorestat_action(raw_text)
    if action is None:
        return

    logger.info(
        "Received scorestat command from user {} in group {}",
        event.user_id,
        event.group_id,
    )
    if action == "help":
        await scorestat_msg.finish(
            "规则：\n"
            "1) 仅统计群名片/昵称中 `分数-名字` 或 `分数—名字`\n"
            "2) 分数范围 350-500\n"
            "3) 5 分一档，从 350 起\n"
            "4) 档位上限 min(500, 最高分+5)"
        )
    await _run_scorestat_with_cooldown(bot, event.group_id, scorestat_msg)


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


def _parse_scorestat_action(raw_text: str) -> str | None:
    normalized = raw_text.strip().replace("／", "/").lower()
    if normalized in {"/scorestat", "scorestat"}:
        return "run"
    if normalized in {"/scorestat help", "scorestat help"}:
        return "help"
    return None


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

    raw_text = str(payload.get("raw_message") or "").strip()
    if not raw_text:
        raw_text = _extract_plain_text_from_message_payload(payload.get("message"))

    action = _parse_scorestat_action(raw_text)
    if action is None:
        return

    logger.info("Received self-sent scorestat command in group {}", group_id)
    if action == "help":
        await bot.send_group_msg(
            group_id=group_id,
            message=(
                "规则：\n"
                "1) 仅统计群名片/昵称中 `分数-名字` 或 `分数—名字`\n"
                "2) 分数范围 350-500\n"
                "3) 5 分一档，从 350 起\n"
                "4) 档位上限 min(500, 最高分+5)"
            ),
        )
        return
    await _run_scorestat_with_cooldown(bot, group_id, scorestat_sent_msg)

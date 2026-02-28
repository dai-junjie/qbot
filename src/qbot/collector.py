from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from nonebot.adapters.onebot.v11 import Bot


async def get_group_members(bot: Bot, group_id: int) -> Sequence[dict[str, Any]]:
    data = await bot.call_api("get_group_member_list", group_id=group_id)
    if isinstance(data, list):
        return data
    return []

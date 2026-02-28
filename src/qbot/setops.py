from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from qbot.parser import parse_member_card

_ZHEJI_PATTERN = re.compile(r"^\s*26\s*[-—]\s*[^-—]+\s*[-—]\s*(\d{3})\s*[-—]\s*.+\s*$")


def member_profile_text(member: dict[str, Any]) -> str:
    card = str(member.get("card") or "").strip()
    if card:
        return card
    return str(member.get("nickname") or "").strip()


def is_zheruan_candidate(profile_text: str) -> bool:
    return parse_zheruan_score(profile_text) is not None


def is_zheji_candidate(profile_text: str) -> bool:
    return parse_zheji_score(profile_text) is not None


def parse_zheruan_score(profile_text: str) -> int | None:
    parsed = parse_member_card(profile_text)
    if parsed is None:
        return None
    return parsed.score


def parse_zheji_score(profile_text: str) -> int | None:
    m = _ZHEJI_PATTERN.match(profile_text.strip())
    if not m:
        return None
    score = int(m.group(1))
    if score < 350 or score > 500:
        return None
    return score


def collect_candidates(
    members: Sequence[dict[str, Any]],
    matcher: Callable[[str], bool],
) -> dict[int, str]:
    candidates: dict[int, str] = {}
    for member in members:
        user_id = member.get("user_id")
        if not isinstance(user_id, int):
            continue
        profile = member_profile_text(member)
        if not profile or not matcher(profile):
            continue
        candidates[user_id] = profile
    return candidates


def build_overlap_text(
    local_group_id: int,
    zheji_group_id: int,
    local_candidates: dict[int, str],
    zheji_candidates: dict[int, str],
) -> str:
    _ = (local_group_id, zheji_group_id)
    overlap_ids = sorted(set(local_candidates) & set(zheji_candidates))

    lines = [
        "跨群考生重合检测：浙软 vs 浙计",
        f"浙软考生数：{len(local_candidates)}",
        f"浙计考生数：{len(zheji_candidates)}",
        f"重合人数：{len(overlap_ids)}",
    ]
    if not overlap_ids:
        lines.append("未发现重合 QQ。")
        return "\n".join(lines)

    lines.append("重合 QQ 列表：")
    for user_id in overlap_ids:
        lines.append(
            f"{user_id} | 浙软:{local_candidates[user_id]} | 浙计:{zheji_candidates[user_id]}"
        )
    return "\n".join(lines)

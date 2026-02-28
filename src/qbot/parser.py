from __future__ import annotations

import re

from qbot.models import ParsedMember

PATTERN = re.compile(r"^\s*(\d{1,3})\s*[-—]\s*(.+?)\s*$")


def parse_member_card(card_or_nickname: str) -> ParsedMember | None:
    text = (card_or_nickname or "").strip()
    if not text:
        return None

    match = PATTERN.match(text)
    if not match:
        return None

    score = int(match.group(1))
    name = match.group(2).strip()

    if not name:
        return None
    if score < 350 or score > 500:
        return None

    return ParsedMember(score=score, name=name, raw_card=text)

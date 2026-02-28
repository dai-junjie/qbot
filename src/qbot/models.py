from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ParsedMember:
    score: int
    name: str
    raw_card: str


@dataclass(slots=True)
class BucketCount:
    start: int
    end: int
    count: int


@dataclass(slots=True)
class SnapshotMeta:
    id: int
    group_id: int
    collected_at: datetime
    valid_member_count: int
    max_score: int
    upper_bound: int

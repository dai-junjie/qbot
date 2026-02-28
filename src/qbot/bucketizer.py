from __future__ import annotations

from collections import Counter

from qbot.models import BucketCount, ParsedMember


def compute_upper_bound(scores: list[int]) -> int | None:
    if not scores:
        return None
    return min(500, max(scores) + 5)


def build_buckets(members: list[ParsedMember]) -> tuple[list[BucketCount], int | None]:
    if not members:
        return [], None

    scores = [m.score for m in members]
    upper = compute_upper_bound(scores)
    assert upper is not None

    counts = Counter()
    for score in scores:
        start = ((score - 350) // 5) * 5 + 350
        end = min(start + 4, upper)
        counts[(start, end)] += 1

    buckets: list[BucketCount] = []
    cur = 350
    while cur <= upper:
        end = min(cur + 4, upper)
        buckets.append(BucketCount(start=cur, end=end, count=counts.get((cur, end), 0)))
        cur += 5

    return buckets, upper

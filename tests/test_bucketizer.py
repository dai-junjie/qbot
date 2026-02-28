from qbot.bucketizer import build_buckets, compute_upper_bound
from qbot.models import ParsedMember


def _member(score: int, name: str) -> ParsedMember:
    return ParsedMember(score=score, name=name, raw_card=f"{score}-{name}")


def test_compute_upper_bound() -> None:
    assert compute_upper_bound([]) is None
    assert compute_upper_bound([350, 420, 495]) == 500
    assert compute_upper_bound([350, 420, 440]) == 445


def test_build_buckets_upper_bound_not_500() -> None:
    members = [_member(350, "A"), _member(352, "B"), _member(440, "C")]
    buckets, upper = build_buckets(members)

    assert upper == 445
    assert buckets[0].start == 350 and buckets[0].end == 354 and buckets[0].count == 2
    assert buckets[-1].start == 445 and buckets[-1].end == 445


def test_build_buckets_empty() -> None:
    buckets, upper = build_buckets([])
    assert buckets == []
    assert upper is None

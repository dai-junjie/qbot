from qbot.analyzer import summarize
from qbot.models import BucketCount


def test_summarize_no_data() -> None:
    text = summarize(
        [],
        0,
        None,
        rank_202_score=None,
        rank_retest_score=None,
        retest_rank=263,
    )
    assert "无有效分数数据" in text


def test_summarize_with_delta() -> None:
    buckets = [
        BucketCount(start=350, end=354, count=1),
        BucketCount(start=355, end=359, count=3),
        BucketCount(start=360, end=364, count=2),
    ]
    text = summarize(
        buckets,
        valid_count=6,
        prev_valid_count=4,
        rank_202_score=None,
        rank_retest_score=None,
        retest_rank=263,
    )
    assert "=== 群成员分数累计统计 ===" in text
    assert "有效样本：6（较上次增加 2 人。）" in text
    assert "复录比计算：202*1.3=262.6，向上取整=263" in text
    assert "关键位次：第202名=样本不足，第263名(202*1.3向上取整)=样本不足" in text
    assert "较上次增加 2 人" in text
    assert "≥ 360分: 2人 (33.3%)" in text
    assert "≥ 355分: 5人 (83.3%)" in text
    assert "≥ 350分: 6人 (100.0%)" in text


def test_separator_after_retest_bucket() -> None:
    buckets = [
        BucketCount(start=350, end=354, count=10),
        BucketCount(start=355, end=359, count=12),
        BucketCount(start=360, end=364, count=19),
        BucketCount(start=365, end=369, count=22),
    ]
    text = summarize(
        buckets,
        valid_count=63,
        prev_valid_count=63,
        rank_202_score=None,
        rank_retest_score=362,
        retest_rank=263,
    )
    lines = text.splitlines()
    idx_bucket = lines.index("≥ 360分: 41人 (65.1%)")
    assert lines[idx_bucket + 1] == "-------------------------"

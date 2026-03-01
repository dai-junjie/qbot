from qbot.analyzer import summarize
from qbot.models import BucketCount


def test_summarize_no_data() -> None:
    text = summarize(
        [],
        0,
        None,
        rank_202_score=None,
        rank_retest_score=None,
        rank_273_score=None,
        rank_280_score=None,
        retest_rank=263,
        avg_top_202=None,
        avg_top_263=None,
        avg_top_273=None,
    )
    assert "无有效分数数据" in text


def test_summarize_with_delta() -> None:
    """
    测试带有增量变化的分数汇总功能
    验证汇总文本中是否包含所有预期的统计信息
    """
    # 定义分数段统计桶
    buckets = [
        BucketCount(start=350, end=354, count=1),  # 350-354分区间有1人
        BucketCount(start=355, end=359, count=3),  # 355-359分区间有3人
        BucketCount(start=360, end=364, count=2),  # 360-364分区间有2人
    ]
    # 调用summarize函数生成汇总文本
    text = summarize(
        buckets,
        valid_count=6,           # 当前有效样本数
        prev_valid_count=4,      # 上次有效样本数
        rank_202_score=None,     # 202位次分数
        rank_retest_score=None,  # 复试分数
        rank_273_score=None,     # 273位次分数
        rank_280_score=None,     # 280位次分数
        retest_rank=263,         # 复试线位次
        avg_top_202=None,        # 前202名平均分
        avg_top_263=None,
        avg_top_273=None,        # 前273名平均分
    )

    # 验证汇总文本中包含的各个统计信息
    assert "=== 群成员分数累计统计 ===" in text  # 验证标题存在
    assert "有效样本：6（较上次增加 2 人。）" in text  # 验证样本数统计  # 验证复试线位次
    assert "复试线位次：第263名" in text
    assert (
        "关键位次：第202名=样本不足，第263名=样本不足，第273名=样本不足，第280名=样本不足"
        in text
    )  # 验证关键位次
    assert "较上次增加 2 人" in text  # 验证增量变化
    assert "≥ 360分: 2人 (33.3%)" in text  # 验证360分以上人数及占比
    assert "≥ 355分: 5人 (83.3%)" in text  # 验证355分以上人数及占比
    assert "≥ 350分: 6人 (100.0%)" in text  # 验证350分以上人数及占比
    assert "前202均分：样本不足" in text  # 验证前202名均分
    assert "前263均分：样本不足" in text  # 验证前263名均分
    assert "前273均分：样本不足" in text  # 验证前273名均分


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
        rank_273_score=None,
        rank_280_score=None,
        retest_rank=263,
        avg_top_202=None,
        avg_top_263=None,
        avg_top_273=None,
    )
    lines = text.splitlines()
    idx_bucket = lines.index("≥ 360分: 41人 (65.1%)")
    assert lines[idx_bucket + 1] == "-------------------------"

from __future__ import annotations

from qbot.models import BucketCount


def _trend_text(current: int, prev: int | None) -> str:
    if prev is None:
        return "首次统计，暂无环比。"
    delta = current - prev
    if delta > 0:
        return f"较上次增加 {delta} 人。"
    if delta < 0:
        return f"较上次减少 {abs(delta)} 人。"
    return "较上次持平。"


def summarize(
    buckets: list[BucketCount],
    valid_count: int,
    prev_valid_count: int | None,
    rank_202_score: int | None,
    rank_retest_score: int | None,
    retest_rank: int,
) -> str:
    if not buckets or valid_count == 0:
        return "本次无有效分数数据（仅统计 350-500 且格式为 分数-名字 / 分数—名字）。"

    # 按阈值做累计统计：>=某分数的人数（从高到低）
    cumulative = 0
    lines = [
        "=== 群成员分数累计统计 ===",
        f"统计范围：350分及以上",
        f"有效样本：{valid_count}（{_trend_text(valid_count, prev_valid_count)}）",
        f"复录比计算：202*1.3={202*1.3:.1f}，向上取整={retest_rank}",
        f"关键位次：第202名={rank_202_score if rank_202_score is not None else '样本不足'}，"
        f"第{retest_rank}名(202*1.3向上取整)={rank_retest_score if rank_retest_score is not None else '样本不足'}",
        "----------------------",
    ]

    retest_bucket_start: int | None = None
    if rank_retest_score is not None:
        retest_bucket_start = ((rank_retest_score - 350) // 5) * 5 + 350

    for b in reversed(buckets):
        cumulative += b.count
        if cumulative == 0:
            continue
        pct = (cumulative / valid_count) * 100
        lines.append(f"≥ {b.start}分: {cumulative}人 ({pct:.1f}%)")
        if retest_bucket_start is not None and b.start == retest_bucket_start:
            lines.append("-------------------------")

    if valid_count < 5:
        lines.append("提醒：样本较少，解读需谨慎。")

    return "\n".join(lines)

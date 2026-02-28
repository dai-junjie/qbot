from __future__ import annotations


def rank_and_percentile(
    sorted_scores: list[int], own_score: int
) -> tuple[int, int, int, float]:
    # Competition ranking: rank = 1 + count(scores strictly higher than own score)
    higher_count = sum(1 for s in sorted_scores if s > own_score)
    tie_count = sum(1 for s in sorted_scores if s == own_score)
    best_rank = 1 + higher_count
    worst_rank = best_rank + tie_count - 1
    # Cumulative percentile from high score to low score:
    # percentage of members whose score is >= own_score.
    percentile = ((higher_count + tie_count) / len(sorted_scores)) * 100
    return best_rank, worst_rank, tie_count, percentile

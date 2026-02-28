from qbot.ranker import rank_and_percentile


def test_rank_and_percentile_basic() -> None:
    scores = [420, 410, 410, 390, 380]
    best_rank, worst_rank, tie_count, percentile = rank_and_percentile(scores, 410)
    assert best_rank == 2
    assert worst_rank == 3
    assert tie_count == 2
    assert round(percentile, 1) == 60.0


def test_rank_and_percentile_top() -> None:
    scores = [450, 430, 420]
    best_rank, worst_rank, tie_count, percentile = rank_and_percentile(scores, 450)
    assert best_rank == 1
    assert worst_rank == 1
    assert tie_count == 1
    assert round(percentile, 1) == 33.3

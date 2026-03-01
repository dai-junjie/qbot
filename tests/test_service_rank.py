from qbot.ranker import rank_and_percentile
from qbot.service import _build_comeback_analysis, _required_coding_delta_for_written_gap


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


def test_required_coding_delta_for_written_gap() -> None:
    assert _required_coding_delta_for_written_gap(0) == 0
    assert _required_coding_delta_for_written_gap(1) == 3
    assert _required_coding_delta_for_written_gap(5) == 12
    assert _required_coding_delta_for_written_gap(120) == 280


def test_build_comeback_analysis_for_chasing_case() -> None:
    lines = _build_comeback_analysis(
        own_score=380,
        target_rank_score=400,
        avg_top_202=395.45,
    )
    text = "\n".join(lines)
    assert "[202线] 目标初试400，当前差20分 -> 机考约+47分" in text
    assert "[202均分] 均分395.45，当前差15.45分 -> 机考约+37分" in text


def test_build_comeback_analysis_for_ahead_case() -> None:
    lines = _build_comeback_analysis(
        own_score=405,
        target_rank_score=400,
        avg_top_202=395.45,
    )
    text = "\n".join(lines)
    assert "[202线] 初试已不低于400 -> 机考约-12分仍可追平" in text
    assert "[202均分] 初试已不低于395.45 -> 机考约-23分仍可追平" in text


def test_build_comeback_analysis_no_hard_cap_for_large_gap() -> None:
    lines = _build_comeback_analysis(
        own_score=350,
        target_rank_score=378,
        avg_top_202=470.0,
    )
    text = "\n".join(lines)
    assert "机考约+280分" in text
    assert "机考追分值不设上限" in text

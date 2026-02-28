from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from pathlib import Path

from qbot.analyzer import summarize
from qbot.bucketizer import build_buckets
from qbot.collector import get_group_members
from qbot.models import BucketCount
from qbot.parser import parse_member_card
from qbot.plotter import render_bucket_chart, render_trend_chart
from qbot.repository import ScoreRepository


@dataclass(slots=True)
class StatResult:
    summary_text: str
    bucket_image: Path | None
    trend_image: Path | None
    buckets: list[BucketCount]


class ScoreStatService:
    def __init__(
        self,
        repository: ScoreRepository,
        history_window_hours: int,
        retention_days: int,
        font_path: str | None,
    ) -> None:
        self.repo = repository
        self.history_window_hours = history_window_hours
        self.retention_days = retention_days
        self.font_path = font_path

    async def run_once(self, bot, group_id: int) -> StatResult:
        members = await get_group_members(bot, group_id)
        parsed = []
        for m in members:
            raw = str(m.get("card") or m.get("nickname") or "")
            item = parse_member_card(raw)
            if item:
                parsed.append(item)

        buckets, upper_bound = build_buckets(parsed)
        prev_valid = await self.repo.get_last_valid_count(group_id)

        if not parsed or upper_bound is None:
            summary = summarize(
                [],
                0,
                prev_valid,
                rank_202_score=None,
                rank_retest_score=None,
                retest_rank=ceil(202 * 1.3),
            )
            return StatResult(summary, None, None, [])

        max_score = max(p.score for p in parsed)
        snapshot = await self.repo.insert_snapshot(
            group_id=group_id,
            valid_member_count=len(parsed),
            max_score=max_score,
            upper_bound=upper_bound,
            buckets=buckets,
        )
        await self.repo.cleanup_old(self.retention_days)

        sorted_scores = sorted((p.score for p in parsed), reverse=True)
        retest_rank = ceil(202 * 1.3)
        rank_202_score = sorted_scores[201] if len(sorted_scores) >= 202 else None
        rank_retest_score = (
            sorted_scores[retest_rank - 1] if len(sorted_scores) >= retest_rank else None
        )

        summary = summarize(
            buckets,
            len(parsed),
            prev_valid,
            rank_202_score=rank_202_score,
            rank_retest_score=rank_retest_score,
            retest_rank=retest_rank,
        )

        output_dir = Path("data/charts") / str(group_id)
        stamp = snapshot.collected_at.strftime("%Y%m%d_%H%M%S")

        bucket_path = render_bucket_chart(
            output_path=output_dir / f"bucket_{stamp}.png",
            buckets=buckets,
            group_id=group_id,
            collected_at=datetime.now(UTC),
            font_path=self.font_path,
        )
        trend_points = await self.repo.get_trend_points(group_id, self.history_window_hours)
        trend_path = render_trend_chart(
            output_path=output_dir / f"trend_{stamp}.png",
            points=trend_points,
            group_id=group_id,
            window_hours=self.history_window_hours,
            font_path=self.font_path,
        )

        return StatResult(summary, bucket_path, trend_path, buckets)

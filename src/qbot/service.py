from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from qbot.analyzer import summarize
from qbot.bucketizer import build_buckets
from qbot.collector import get_group_members
from qbot.models import BucketCount
from qbot.parser import parse_member_card
from qbot.plotter import render_bucket_chart, render_trend_chart
from qbot.ranker import rank_and_percentile
from qbot.repository import ScoreRepository


@dataclass(slots=True)
class StatResult:
    summary_text: str
    bucket_image: Path | None
    trend_image: Path | None
    buckets: list[BucketCount]


@dataclass(slots=True)
class RankResult:
    text: str


RETEST_RANK = 263


def _avg_top_n(scores_desc: list[int], n: int) -> float | None:
    if len(scores_desc) < n:
        return None
    return sum(scores_desc[:n]) / n


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
                retest_rank=RETEST_RANK,
                avg_top_202=None,
                avg_top_263=None,
                avg_top_273=None,
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
        retest_rank = RETEST_RANK
        rank_202_score = sorted_scores[201] if len(sorted_scores) >= 202 else None
        rank_retest_score = (
            sorted_scores[retest_rank - 1] if len(sorted_scores) >= retest_rank else None
        )
        avg_top_202 = _avg_top_n(sorted_scores, 202)
        avg_top_263 = _avg_top_n(sorted_scores, 263)
        avg_top_273 = _avg_top_n(sorted_scores, 273)

        summary = summarize(
            buckets,
            len(parsed),
            prev_valid,
            rank_202_score=rank_202_score,
            rank_retest_score=rank_retest_score,
            retest_rank=retest_rank,
            avg_top_202=avg_top_202,
            avg_top_263=avg_top_263,
            avg_top_273=avg_top_273,
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

    async def query_self_rank(self, bot, group_id: int, user_id: int) -> RankResult:
        members = await get_group_members(bot, group_id)

        parsed_scores: list[int] = []
        self_parsed = None
        self_raw = ""
        self_display_name = ""

        for m in members:
            raw = str(m.get("card") or m.get("nickname") or "")
            uid = int(m.get("user_id") or 0)
            parsed = parse_member_card(raw)

            if uid == user_id:
                self_raw = raw
                self_parsed = parsed
                self_display_name = str(m.get("card") or m.get("nickname") or "").strip()
            if parsed:
                parsed_scores.append(parsed.score)

        if self_parsed is None:
            if not self_raw:
                return RankResult(
                    "你当前名片/昵称为空，无法查询。请改为 `分数-名字` 或 `分数—名字`（例如 `390-张三`）。"
                )
            return RankResult(
                "你的名片格式不符合要求，无法查询。\n"
                "请使用 `分数-名字` 或 `分数—名字`，且分数范围 350-500（例如 `390-张三`）。"
            )

        if not parsed_scores:
            return RankResult("当前群里没有可用的有效分数样本。")

        sorted_scores = sorted(parsed_scores, reverse=True)
        own_score = self_parsed.score
        valid_count = len(sorted_scores)
        best_rank, worst_rank, tie_count, percentile = rank_and_percentile(
            sorted_scores, own_score
        )

        retest_rank = RETEST_RANK
        retest_score = (
            sorted_scores[retest_rank - 1] if valid_count >= retest_rank else None
        )

        lines = [
            "=== 个人排名查询 ===",
            f"查询人：{self_display_name or user_id}",
            f"你的分数：{own_score}",
            f"你的排名：第{best_rank}/{valid_count}名（同分按最高位次计）",
            f"同分人数：{tie_count}",
            f"你的百分位：{percentile:.1f}%",
        ]
        if tie_count > 1:
            lines.append(
                f"同分位次区间：第{best_rank}-第{worst_rank}名（判定按第{best_rank}名）"
            )

        if retest_score is None:
            lines.append(
                f"复试线判定：样本不足（有效样本 {valid_count} < {retest_rank}，暂无法判定）"
            )
        else:
            # 按“同分最高位次”判定，等价于 own_score >= 复试线分数
            in_line = "是" if own_score >= retest_score else "否"
            lines.append(f"复试线：第{retest_rank}名分数={retest_score}")
            lines.append(f"是否在复试线上：{in_line}")

        return RankResult("\n".join(lines))

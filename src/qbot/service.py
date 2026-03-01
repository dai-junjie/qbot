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
from qbot.plotter import render_dashboard_chart
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
TARGET_RANK = 202

# 2025浙软电子信息复试录取方案：
# 综合成绩=初试总分/5*70% + 复试成绩*30%
# 复试成绩=面试*80% + 机考*20%
# 在“面试同分”假设下，初试1分差距需要约2.333分机考来弥补。
WRITTEN_TO_CODING_RATIO = (0.7 / 5) / (0.3 * 0.2)


def _avg_top_n(scores_desc: list[int], n: int) -> float | None:
    if len(scores_desc) < n:
        return None
    return sum(scores_desc[:n]) / n


def _required_coding_delta_for_written_gap(written_gap: float) -> int:
    if written_gap <= 0:
        return 0
    return ceil(written_gap * WRITTEN_TO_CODING_RATIO)


def _build_comeback_analysis(
    own_score: int,
    target_rank_score: int | None,
    avg_top_202: float | None,
) -> list[str]:
    lines = [
        "=== 复试逆袭分析（按浙软2025口径）===",
        "----------------------",
        "[规则] 综合=初试/5×70% + 复试×30%",
        "[规则] 复试=面试×80% + 机考×20%",
        "[换算] 初试每落后1分 ≈ 机考多2.33分（面试同分假设）",
        "----------------------",
    ]

    if target_rank_score is None:
        lines.append("第202名分析：样本不足，暂无法估算冲刺空间。")
    else:
        gap_to_202 = target_rank_score - own_score
        if gap_to_202 > 0:
            need_202 = _required_coding_delta_for_written_gap(gap_to_202)
            lines.append(
                f"[202线] 目标初试{target_rank_score}，当前差{gap_to_202}分 -> 机考约+{need_202}分"
            )
        else:
            room_202 = _required_coding_delta_for_written_gap(-gap_to_202)
            lines.append(
                f"[202线] 初试已不低于{target_rank_score} -> 机考约-{room_202}分仍可追平"
            )

    if avg_top_202 is None:
        lines.append("前202均分追分：样本不足，暂无法估算。")
    else:
        gap_to_avg_202 = avg_top_202 - own_score
        if gap_to_avg_202 > 0:
            need_avg = _required_coding_delta_for_written_gap(gap_to_avg_202)
            lines.append(
                f"[202均分] 均分{avg_top_202:.2f}，当前差{gap_to_avg_202:.2f}分 -> 机考约+{need_avg}分"
            )
        else:
            room_avg = _required_coding_delta_for_written_gap(-gap_to_avg_202)
            lines.append(
                f"[202均分] 初试已不低于{avg_top_202:.2f} -> 机考约-{room_avg}分仍可追平"
            )

    lines.append("----------------------")
    lines.append("注：机考追分值不设上限，出现 100+ 属于目标难度提示。")
    lines.append("说明：该估算仅用于策略参考，实际录取受面试、同分排序规则等因素影响。")
    return lines


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
                rank_273_score=None,
                rank_280_score=None,
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
        rank_273_score = sorted_scores[272] if len(sorted_scores) >= 273 else None
        rank_280_score = sorted_scores[279] if len(sorted_scores) >= 280 else None
        avg_top_202 = _avg_top_n(sorted_scores, 202)
        avg_top_263 = _avg_top_n(sorted_scores, 263)
        avg_top_273 = _avg_top_n(sorted_scores, 273)

        summary = summarize(
            buckets,
            len(parsed),
            prev_valid,
            rank_202_score=rank_202_score,
            rank_retest_score=rank_retest_score,
            rank_273_score=rank_273_score,
            rank_280_score=rank_280_score,
            retest_rank=retest_rank,
            avg_top_202=avg_top_202,
            avg_top_263=avg_top_263,
            avg_top_273=avg_top_273,
        )

        output_dir = Path("data/charts") / str(group_id)
        stamp = snapshot.collected_at.strftime("%Y%m%d_%H%M%S")

        trend_points = await self.repo.get_trend_points(group_id, self.history_window_hours)
        dashboard_path = render_dashboard_chart(
            output_path=output_dir / f"dashboard_{stamp}.png",
            buckets=buckets,
            points=trend_points,
            group_id=group_id,
            collected_at=datetime.now(UTC),
            window_hours=self.history_window_hours,
            font_path=self.font_path,
        )
        return StatResult(summary, dashboard_path, None, buckets)

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
            in_line = "是" if own_score >= retest_score else "否"
            lines.append(f"复试线：第{retest_rank}名分数={retest_score}")
            lines.append(f"是否在复试线上：{in_line}")

        # Reverse-analysis module is temporarily disabled for /rank output.
        # lines.append("")
        # lines.extend(
        #     _build_comeback_analysis(
        #         own_score=own_score,
        #         target_rank_score=target_rank_score,
        #         avg_top_202=avg_top_202,
        #     )
        # )

        return RankResult("\n".join(lines))

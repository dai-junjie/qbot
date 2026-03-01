from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator

from qbot.models import BucketCount

DONUT_TEMPERATURE = 1.8
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _apply_font(font_path: str | None) -> None:
    if font_path:
        font_manager.fontManager.addfont(font_path)
        name = font_manager.FontProperties(fname=font_path).get_name()
        plt.rcParams["font.sans-serif"] = [name]
    plt.rcParams["axes.unicode_minus"] = False


def _to_beijing(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(BEIJING_TZ)


def _temperature_scaled_weights(values: list[int], temperature: float) -> list[float]:
    if not values:
        return []
    if temperature <= 0:
        raise ValueError("temperature must be > 0")
    total = sum(values)
    if total <= 0:
        return [0.0 for _ in values]
    alpha = 1.0 / temperature
    probs = [v / total for v in values]
    scaled = [p**alpha if p > 0 else 0.0 for p in probs]
    scaled_sum = sum(scaled)
    if scaled_sum <= 0:
        return [0.0 for _ in values]
    return [x / scaled_sum for x in scaled]


def render_bucket_chart(
    output_path: Path,
    buckets: list[BucketCount],
    group_id: int,
    collected_at: datetime,
    font_path: str | None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _apply_font(font_path)

    # Visualization-only trim: drop trailing empty bins above current max score.
    plot_buckets = list(buckets)
    while plot_buckets and plot_buckets[-1].count == 0:
        plot_buckets.pop()
    if not plot_buckets:
        plot_buckets = list(buckets)

    labels = [f"{b.start}-{b.end}" for b in plot_buckets]
    values = [b.count for b in plot_buckets]
    total = sum(values)

    # Cumulative rank for 5-point bins (>= current bin).
    cumulative_ge: list[int] = []
    running = 0
    for v in reversed(values):
        running += v
        cumulative_ge.append(running)
    cumulative_ge.reverse()

    # Aggregate into 10-point bins: 350-359, 360-369, ...
    agg_10: dict[int, int] = {}
    for b in plot_buckets:
        start_10 = (b.start // 10) * 10
        agg_10[start_10] = agg_10.get(start_10, 0) + b.count
    labels_10 = [f"{start}-{start + 9}" for start in sorted(agg_10)]
    values_10 = [agg_10[start] for start in sorted(agg_10)]
    pct_10 = [v / total * 100 if total > 0 else 0.0 for v in values_10]

    collected_at_bj = _to_beijing(collected_at)
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(18, 6))
    fig.suptitle(
        f"Group {group_id} Score Distribution ({collected_at_bj.strftime('%Y-%m-%d %H:%M')} BJT)",
        fontsize=14,
    )
    fig.subplots_adjust(wspace=0.25)

    bars = ax_left.bar(labels, values, color="#2979FF", alpha=0.9)
    ax_left.set_title("5-Point Bins: Count + Cumulative Rank")
    ax_left.set_xlabel("Score Bin")
    ax_left.set_ylabel("Count")
    ax_left.set_ylim(0, max(values + [0]) + 4)
    for bar, value in zip(bars, values, strict=False):
        ax_left.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.2,
            str(value),
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ax_cum = ax_left.twinx()
    ax_cum.plot(labels, cumulative_ge, color="#D32F2F", marker="o", linewidth=1.5)
    ax_cum.set_ylabel("Cumulative Rank (>= bin)")
    ax_cum.set_ylim(0, max(cumulative_ge + [0]) + 10)
    for i, cum in enumerate(cumulative_ge):
        ax_cum.text(i, cum + 2, str(cum), color="#B71C1C", ha="center", fontsize=7)
    ax_left.tick_params(axis="x", rotation=45, pad=8)
    ax_left.set_xlabel("Score Bin", fontsize=10)

    ax_right.set_title("10-Point Bins Donut (Temp-scaled Area, Raw % Labels)")
    if total > 0 and any(values_10):
        color_maps = ["tab20", "Set3", "Paired"]
        colors: list[tuple[float, float, float, float]] = []
        needed = len(values_10)
        for cmap_name in color_maps:
            cmap = plt.get_cmap(cmap_name)
            colors.extend([cmap(i) for i in range(cmap.N)])
            if len(colors) >= needed:
                break
        if len(colors) < needed:
            fallback = plt.get_cmap("hsv")
            colors.extend(fallback(i / needed) for i in range(needed - len(colors)))
        colors = colors[:needed]

        scaled_weights = _temperature_scaled_weights(values_10, DONUT_TEMPERATURE)

        label_with_count = [
            f"{label}\nN={count}"
            for label, count in zip(labels_10, values_10, strict=False)
        ]

        pct_idx = {"i": 0}

        def _autopct(_pct: float) -> str:
            i = pct_idx["i"]
            pct_idx["i"] += 1
            if i >= len(pct_10):
                return ""
            return f"{pct_10[i]:.1f}%"

        ax_right.pie(
            scaled_weights,
            labels=label_with_count,
            autopct=_autopct,
            startangle=90,
            colors=colors,
            wedgeprops={"width": 0.42, "edgecolor": "white"},
            labeldistance=1.08,
            pctdistance=0.78,
            textprops={"fontsize": 8},
        )
        ax_right.text(
            0,
            0,
            f"Total\n{total}\nT={DONUT_TEMPERATURE:.1f}",
            ha="center",
            va="center",
            fontsize=10,
            color="#1b5e20",
            weight="bold",
        )
        ax_right.set_aspect("equal")
    else:
        ax_right.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax_right.transAxes)
        ax_right.axis("off")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def render_trend_chart(
    output_path: Path,
    points: list[tuple[datetime, int]],
    group_id: int,
    window_hours: int,
    font_path: str | None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _apply_font(font_path)

    fig, ax = plt.subplots(figsize=(12, 5))
    if points:
        xs = [_to_beijing(p[0]) for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, marker="o", color="#00A86B")
    ax.set_title(f"Group {group_id} Valid Members Trend (Last {window_hours}h, BJT)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Valid Count")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def render_dashboard_chart(
    output_path: Path,
    buckets: list[BucketCount],
    points: list[tuple[datetime, int]],
    group_id: int,
    collected_at: datetime,
    window_hours: int,
    font_path: str | None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _apply_font(font_path)

    plot_buckets = list(buckets)
    while plot_buckets and plot_buckets[-1].count == 0:
        plot_buckets.pop()
    if not plot_buckets:
        plot_buckets = list(buckets)

    labels = [f"{b.start}-{b.end}" for b in plot_buckets]
    values = [b.count for b in plot_buckets]
    total = sum(values)

    cumulative_ge: list[int] = []
    running = 0
    for v in reversed(values):
        running += v
        cumulative_ge.append(running)
    cumulative_ge.reverse()

    agg_10: dict[int, int] = {}
    for b in plot_buckets:
        start_10 = (b.start // 10) * 10
        agg_10[start_10] = agg_10.get(start_10, 0) + b.count
    labels_10 = [f"{start}-{start + 9}" for start in sorted(agg_10)]
    values_10 = [agg_10[start] for start in sorted(agg_10)]
    pct_10 = [v / total * 100 if total > 0 else 0.0 for v in values_10]

    collected_at_bj = _to_beijing(collected_at)
    fig = plt.figure(figsize=(18, 11.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[2.0, 1.1], hspace=0.55, wspace=0.25)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    ax_bottom = fig.add_subplot(gs[1, :])
    fig.suptitle(
        f"Group {group_id} Statistical Dashboard ({collected_at_bj.strftime('%Y-%m-%d %H:%M')} BJT)",
        fontsize=14,
    )

    bars = ax_left.bar(labels, values, color="#2979FF", alpha=0.9)
    ax_left.set_title("5-Point Bins: Count + Cumulative Rank")
    ax_left.set_xlabel("Score Bin")
    ax_left.set_ylabel("Count")
    ax_left.set_ylim(0, max(values + [0]) + 4)
    for bar, value in zip(bars, values, strict=False):
        ax_left.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.2,
            str(value),
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax_cum = ax_left.twinx()
    ax_cum.plot(labels, cumulative_ge, color="#D32F2F", marker="o", linewidth=1.5)
    ax_cum.set_ylabel("Cumulative Rank (>= bin)")
    ax_cum.set_ylim(0, max(cumulative_ge + [0]) + 10)
    for i, cum in enumerate(cumulative_ge):
        ax_cum.text(i, cum + 2, str(cum), color="#B71C1C", ha="center", fontsize=7)
    ax_left.tick_params(axis="x", rotation=35, pad=10, labelsize=9)
    ax_left.set_xlabel("Score Bin", fontsize=10)

    ax_right.set_title("10-Point Bins Donut (Temp-scaled Area, Raw % Labels)")
    if total > 0 and any(values_10):
        color_maps = ["tab20", "Set3", "Paired"]
        colors: list[tuple[float, float, float, float]] = []
        needed = len(values_10)
        for cmap_name in color_maps:
            cmap = plt.get_cmap(cmap_name)
            colors.extend([cmap(i) for i in range(cmap.N)])
            if len(colors) >= needed:
                break
        if len(colors) < needed:
            fallback = plt.get_cmap("hsv")
            colors.extend(fallback(i / needed) for i in range(needed - len(colors)))
        colors = colors[:needed]
        scaled_weights = _temperature_scaled_weights(values_10, DONUT_TEMPERATURE)
        label_with_count = [
            f"{label}\nN={count}"
            for label, count in zip(labels_10, values_10, strict=False)
        ]
        pct_idx = {"i": 0}

        def _autopct(_pct: float) -> str:
            i = pct_idx["i"]
            pct_idx["i"] += 1
            if i >= len(pct_10):
                return ""
            return f"{pct_10[i]:.1f}%"

        ax_right.pie(
            scaled_weights,
            labels=label_with_count,
            autopct=_autopct,
            startangle=90,
            colors=colors,
            wedgeprops={"width": 0.42, "edgecolor": "white"},
            labeldistance=1.08,
            pctdistance=0.78,
            textprops={"fontsize": 8},
        )
        ax_right.text(
            0,
            0,
            f"Total\n{total}\nT={DONUT_TEMPERATURE:.1f}",
            ha="center",
            va="center",
            fontsize=10,
            color="#1b5e20",
            weight="bold",
        )
        ax_right.set_aspect("equal")
    else:
        ax_right.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax_right.transAxes)
        ax_right.axis("off")

    if points:
        xs = [_to_beijing(p[0]) for p in points]
        ys = [p[1] for p in points]
        ax_bottom.plot(xs, ys, marker="o", color="#00A86B")
    ax_bottom.set_title(f"Valid Members Trend (Last {window_hours}h, BJT)")
    ax_bottom.set_xlabel("Time")
    ax_bottom.set_ylabel("Valid Count")
    ax_bottom.yaxis.set_major_locator(MaxNLocator(integer=True))
    for label in ax_bottom.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")
    ax_bottom.tick_params(axis="x", pad=8)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95], h_pad=2.2)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path

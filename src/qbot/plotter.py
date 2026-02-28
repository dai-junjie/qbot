from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from qbot.models import BucketCount


def _apply_font(font_path: str | None) -> None:
    if font_path:
        font_manager.fontManager.addfont(font_path)
        name = font_manager.FontProperties(fname=font_path).get_name()
        plt.rcParams["font.sans-serif"] = [name]
    plt.rcParams["axes.unicode_minus"] = False


def render_bucket_chart(
    output_path: Path,
    buckets: list[BucketCount],
    group_id: int,
    collected_at: datetime,
    font_path: str | None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _apply_font(font_path)

    labels = [f"{b.start}-{b.end}" for b in buckets]
    values = [b.count for b in buckets]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(labels, values, color="#2979FF")
    ax.set_title(
        f"Group {group_id} Score Distribution ({collected_at.strftime('%Y-%m-%d %H:%M')})"
    )
    ax.set_xlabel("Score Bin")
    ax.set_ylabel("Count")
    ax.set_ylim(0, max(values + [0]) + 2)
    for bar, value in zip(bars, values, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.05,
            str(value),
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.tick_params(axis="x", rotation=45)
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
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, marker="o", color="#00A86B")
    ax.set_title(f"Group {group_id} Valid Members Trend (Last {window_hours}h)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Valid Count")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path

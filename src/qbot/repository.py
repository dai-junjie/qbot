from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from qbot.models import BucketCount, SnapshotMeta


class ScoreRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS score_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    collected_at TEXT NOT NULL,
                    valid_member_count INTEGER NOT NULL,
                    max_score INTEGER NOT NULL,
                    upper_bound INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS score_buckets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    bucket_start INTEGER NOT NULL,
                    bucket_end INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES score_snapshots(id)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_group_time
                ON score_snapshots(group_id, collected_at);
                """
            )
            await db.commit()

    async def insert_snapshot(
        self,
        group_id: int,
        valid_member_count: int,
        max_score: int,
        upper_bound: int,
        buckets: list[BucketCount],
    ) -> SnapshotMeta:
        collected_at = datetime.now(UTC)
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO score_snapshots (
                    group_id, collected_at, valid_member_count, max_score, upper_bound
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, collected_at.isoformat(), valid_member_count, max_score, upper_bound),
            )
            snapshot_id = cursor.lastrowid
            assert snapshot_id is not None

            await db.executemany(
                """
                INSERT INTO score_buckets (snapshot_id, bucket_start, bucket_end, count)
                VALUES (?, ?, ?, ?)
                """,
                [(snapshot_id, b.start, b.end, b.count) for b in buckets],
            )
            await db.commit()

        return SnapshotMeta(
            id=int(snapshot_id),
            group_id=group_id,
            collected_at=collected_at,
            valid_member_count=valid_member_count,
            max_score=max_score,
            upper_bound=upper_bound,
        )

    async def get_last_valid_count(self, group_id: int) -> int | None:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT valid_member_count
                FROM score_snapshots
                WHERE group_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (group_id,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else None

    async def get_trend_points(
        self, group_id: int, window_hours: int
    ) -> list[tuple[datetime, int]]:
        since = datetime.now(UTC) - timedelta(hours=window_hours)
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT collected_at, valid_member_count
                FROM score_snapshots
                WHERE group_id = ? AND collected_at >= ?
                ORDER BY collected_at ASC
                """,
                (group_id, since.isoformat()),
            )
            rows = await cursor.fetchall()

        points: list[tuple[datetime, int]] = []
        for collected_at, count in rows:
            points.append((datetime.fromisoformat(collected_at), int(count)))
        return points

    async def cleanup_old(self, retention_days: int) -> None:
        threshold = datetime.now(UTC) - timedelta(days=retention_days)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                DELETE FROM score_buckets
                WHERE snapshot_id IN (
                    SELECT id FROM score_snapshots WHERE collected_at < ?
                )
                """,
                (threshold.isoformat(),),
            )
            await db.execute(
                "DELETE FROM score_snapshots WHERE collected_at < ?",
                (threshold.isoformat(),),
            )
            await db.commit()

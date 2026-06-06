from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Channel:
    id: int
    channel_id: int
    username: str | None
    title: str
    is_active: bool
    last_post_at: str | None
    last_error: str | None
    posts_count: int


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def connect(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        return conn

    async def init(self) -> None:
        async with await self.connect() as conn:
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    title TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_post_at TEXT,
                    last_error TEXT,
                    posts_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS post_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS run_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    total INTEGER NOT NULL DEFAULT 0,
                    success INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            await conn.commit()

    async def upsert_channel(
        self,
        channel_id: int,
        title: str,
        username: str | None,
    ) -> None:
        async with await self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO channels (channel_id, title, username, is_active)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(channel_id) DO UPDATE SET
                    title = excluded.title,
                    username = excluded.username
                """,
                (channel_id, title, username),
            )
            await conn.commit()

    async def list_active_channels(self, limit: int = 0) -> list[Channel]:
        query = """
            SELECT id, channel_id, username, title, is_active,
                   last_post_at, last_error, posts_count
            FROM channels
            WHERE is_active = 1
            ORDER BY id
        """
        if limit > 0:
            query += f" LIMIT {limit}"

        async with await self.connect() as conn:
            rows = await conn.execute_fetchall(query)
        return [_row_to_channel(row) for row in rows]

    async def mark_post_success(self, channel_id: int) -> None:
        now = datetime.utcnow().isoformat()
        async with await self.connect() as conn:
            await conn.execute(
                """
                UPDATE channels
                SET last_post_at = ?, last_error = NULL, posts_count = posts_count + 1
                WHERE channel_id = ?
                """,
                (now, channel_id),
            )
            await conn.execute(
                """
                INSERT INTO post_log (channel_id, status, message)
                VALUES (?, 'ok', 'posted')
                """,
                (channel_id,),
            )
            await conn.commit()

    async def mark_post_failed(self, channel_id: int, error: str) -> None:
        async with await self.connect() as conn:
            await conn.execute(
                """
                UPDATE channels SET last_error = ? WHERE channel_id = ?
                """,
                (error[:500], channel_id),
            )
            await conn.execute(
                """
                INSERT INTO post_log (channel_id, status, message)
                VALUES (?, 'error', ?)
                """,
                (channel_id, error[:500]),
            )
            await conn.commit()

    async def deactivate_channel(self, channel_id: int, reason: str) -> None:
        async with await self.connect() as conn:
            await conn.execute(
                """
                UPDATE channels
                SET is_active = 0, last_error = ?
                WHERE channel_id = ?
                """,
                (reason[:500], channel_id),
            )
            await conn.commit()

    async def stats(self) -> dict[str, int]:
        async with await self.connect() as conn:
            total = await conn.execute_fetchall(
                "SELECT COUNT(*) AS c FROM channels"
            )
            active = await conn.execute_fetchall(
                "SELECT COUNT(*) AS c FROM channels WHERE is_active = 1"
            )
            posted_today = await conn.execute_fetchall(
                """
                SELECT COUNT(*) AS c FROM channels
                WHERE last_post_at >= date('now')
                """
            )
        return {
            "total": total[0]["c"],
            "active": active[0]["c"],
            "posted_today": posted_today[0]["c"],
        }

    async def start_run(self) -> int:
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "INSERT INTO run_stats (started_at) VALUES (datetime('now'))"
            )
            await conn.commit()
            return cursor.lastrowid

    async def finish_run(self, run_id: int, total: int, success: int, failed: int) -> None:
        async with await self.connect() as conn:
            await conn.execute(
                """
                UPDATE run_stats
                SET finished_at = datetime('now'),
                    total = ?, success = ?, failed = ?
                WHERE id = ?
                """,
                (total, success, failed, run_id),
            )
            await conn.commit()


def _row_to_channel(row: aiosqlite.Row) -> Channel:
    return Channel(
        id=row["id"],
        channel_id=row["channel_id"],
        username=row["username"],
        title=row["title"],
        is_active=bool(row["is_active"]),
        last_post_at=row["last_post_at"],
        last_error=row["last_error"],
        posts_count=row["posts_count"],
    )

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import aiosqlite


def _parse_hm(value: str) -> int:
    h, m = map(int, value.split(":"))
    return h * 60 + m


class DB:
    def __init__(self, path: Path, window_start: str, window_end: str) -> None:
        self.path = path
        self.win_start = _parse_hm(window_start)
        self.win_end = _parse_hm(window_end)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    username TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    schedule_date TEXT,
                    schedule_minute INTEGER,
                    last_post_date TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS post_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    chat_id INTEGER,
                    channel_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'auto'
                );
                CREATE INDEX IF NOT EXISTS idx_post_logs_created ON post_logs(created_at DESC);
                """
            )
            await db.commit()
            await self._migrate(db)

    async def _migrate(self, db: aiosqlite.Connection) -> None:
        cols = {
            row[1]
            for row in await db.execute_fetchall("PRAGMA table_info(channels)")
        }
        if "partial_post_date" not in cols:
            await db.execute(
                "ALTER TABLE channels ADD COLUMN partial_post_date TEXT"
            )
            await db.commit()

    async def set_partial(self, chat_id: int) -> None:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE channels SET partial_post_date=? WHERE chat_id=?",
                (today, chat_id),
            )
            await db.commit()

    async def needs_text_only(self, chat_id: int) -> bool:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall(
                "SELECT partial_post_date FROM channels WHERE chat_id=?",
                (chat_id,),
            )
        return bool(row and row[0][0] == today)

    async def count_partial_today(self) -> int:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall(
                """
                SELECT COUNT(*) FROM channels
                WHERE active=1 AND partial_post_date=?
                """,
                (today,),
            )
        return row[0][0]

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            await db.commit()

    async def get_setting(self, key: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall(
                "SELECT value FROM settings WHERE key=?", (key,)
            )
        return row[0][0] if row else None

    def _new_schedule(self) -> tuple[str, int]:
        day = date.today()
        start, end = self.win_start, self.win_end
        now = datetime.now()
        if now.hour * 60 + now.minute >= end:
            day += timedelta(days=1)
        elif now.hour * 60 + now.minute >= start:
            start = now.hour * 60 + now.minute + 1
        if start > end:
            day += timedelta(days=1)
            start = self.win_start
        return day.isoformat(), random.randint(start, end)

    async def upsert_channel(
        self, chat_id: int, title: str, username: str | None
    ) -> None:
        sched_date, minute = self._new_schedule()
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall(
                "SELECT schedule_date, last_post_date FROM channels WHERE chat_id=?",
                (chat_id,),
            )
            if not row:
                await db.execute(
                    """
                    INSERT INTO channels (chat_id, title, username, active, schedule_date, schedule_minute)
                    VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (chat_id, title, username, sched_date, minute),
                )
            else:
                old_sched, last_post = row[0]
                await db.execute(
                    """
                    UPDATE channels SET title=?, username=?, active=1
                    WHERE chat_id=?
                    """,
                    (title, username, chat_id),
                )
                if last_post != today:
                    sched_date, minute = self._new_schedule()
                    await db.execute(
                        """
                        UPDATE channels SET schedule_date=?, schedule_minute=?
                        WHERE chat_id=?
                        """,
                        (sched_date, minute, chat_id),
                    )
            await db.commit()

    async def deactivate(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE channels SET active=0 WHERE chat_id=?", (chat_id,)
            )
            await db.commit()

    async def delete_channel(self, chat_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "DELETE FROM channels WHERE chat_id=?", (chat_id,)
            )
            await db.commit()
            return cur.rowcount > 0

    async def delete_by_username(self, username: str) -> bool:
        name = username.lstrip("@").lower()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "DELETE FROM channels WHERE lower(username)=?", (name,)
            )
            await db.commit()
            return cur.rowcount > 0

    async def clear_all(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("DELETE FROM channels")
            await db.commit()
            return cur.rowcount

    async def clear_inactive(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("DELETE FROM channels WHERE active=0")
            await db.commit()
            return cur.rowcount

    async def count_inactive(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall(
                "SELECT COUNT(*) FROM channels WHERE active=0"
            )
        return row[0][0]

    async def get_extra_admins(self) -> list[int]:
        raw = await self.get_setting("extra_admin_ids")
        if not raw:
            return []
        return [int(x) for x in raw.split(",") if x.strip().isdigit()]

    async def add_extra_admin(self, user_id: int) -> bool:
        admins = await self.get_extra_admins()
        if user_id in admins:
            return False
        admins.append(user_id)
        await self.set_setting("extra_admin_ids", ",".join(str(x) for x in admins))
        return True

    async def remove_extra_admin(self, user_id: int) -> bool:
        admins = await self.get_extra_admins()
        if user_id not in admins:
            return False
        admins.remove(user_id)
        await self.set_setting("extra_admin_ids", ",".join(str(x) for x in admins))
        return True

    async def get_channel(
        self, chat_id: int
    ) -> tuple[str, str | None, int, str | None, str | None, int] | None:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall(
                """
                SELECT title, username, schedule_minute, schedule_date, last_post_date, active, partial_post_date
                FROM channels WHERE chat_id=?
                """,
                (chat_id,),
            )
        if not row:
            return None
        title, username, minute, sched_date, last_post, active, partial = row[0]
        return title, username, minute, sched_date, last_post, active, partial

    async def regenerate_channel(self, chat_id: int) -> bool:
        sched_date, minute = self._new_schedule()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                UPDATE channels
                SET schedule_date=?, schedule_minute=?, active=1, partial_post_date=NULL
                WHERE chat_id=?
                """,
                (sched_date, minute, chat_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def log_post(
        self,
        chat_id: int,
        channel_name: str,
        status: str,
        detail: str = "",
        source: str = "auto",
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO post_logs (created_at, chat_id, channel_name, status, detail, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, chat_id, channel_name, status, detail[:500], source),
            )
            if status in ("fail", "off", "partial"):
                err = detail or channel_name
                await db.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('last_error', ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (f"{now} · {channel_name}: {err}"[:500],),
                )
            await db.execute(
                "DELETE FROM post_logs WHERE id NOT IN "
                "(SELECT id FROM post_logs ORDER BY id DESC LIMIT 2000)"
            )
            await db.commit()

    async def set_last_error(self, text: str) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self.set_setting("last_error", f"{now} · {text}"[:500])

    async def get_last_error(self) -> str | None:
        return await self.get_setting("last_error")

    async def clear_last_error(self) -> None:
        await self.set_setting("last_error", "")

    async def recent_errors(self, limit: int = 10) -> list[tuple]:
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT created_at, channel_name, detail
                FROM post_logs
                WHERE status IN ('fail', 'off', 'partial')
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        return rows

    async def recent_logs(self, limit: int = 15, offset: int = 0) -> list[tuple]:
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT created_at, channel_name, status, detail, source
                FROM post_logs
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        return rows

    async def logs_count(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            row = await db.execute_fetchall("SELECT COUNT(*) FROM post_logs")
        return row[0][0]

    async def pending_channels(self) -> list[tuple[int, str, str | None]]:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT chat_id, title, username FROM channels
                WHERE active=1
                  AND schedule_date=?
                  AND (last_post_date IS NULL OR last_post_date != ?)
                ORDER BY schedule_minute
                """,
                (today, today),
            )
        return [(r[0], r[1], r[2]) for r in rows]

    async def ensure_today_schedules(self) -> None:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                "SELECT chat_id FROM channels WHERE active=1 AND schedule_date!=?",
                (today,),
            )
            for (chat_id,) in rows:
                sched_date, minute = self._new_schedule()
                await db.execute(
                    "UPDATE channels SET schedule_date=?, schedule_minute=? WHERE chat_id=?",
                    (sched_date, minute, chat_id),
                )
            await db.commit()

    async def regenerate_day(self) -> int:
        day_s = date.today().isoformat()
        count = 0
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                "SELECT chat_id FROM channels WHERE active=1"
            )
            for (chat_id,) in rows:
                minute = random.randint(self.win_start, self.win_end)
                await db.execute(
                    """
                    UPDATE channels
                    SET schedule_date=?, schedule_minute=?, last_post_date=NULL, partial_post_date=NULL
                    WHERE chat_id=? AND active=1
                    """,
                    (day_s, minute, chat_id),
                )
                count += 1
            await db.commit()
        return count

    async def due_channels(self) -> list[tuple[int, str, str | None]]:
        today = date.today().isoformat()
        now_min = datetime.now().hour * 60 + datetime.now().minute
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT chat_id, title, username FROM channels
                WHERE active=1
                  AND schedule_date=?
                  AND schedule_minute <= ?
                  AND (last_post_date IS NULL OR last_post_date != ?)
                ORDER BY schedule_minute
                """,
                (today, now_min, today),
            )
        return [(r[0], r[1], r[2]) for r in rows]

    async def mark_posted(self, chat_id: int) -> None:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE channels
                SET last_post_date=?, partial_post_date=NULL
                WHERE chat_id=?
                """,
                (today, chat_id),
            )
            await db.commit()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self.set_setting("last_ok", now)

    async def stats(self) -> dict:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            total = (await db.execute_fetchall(
                "SELECT COUNT(*) FROM channels WHERE active=1"
            ))[0][0]
            posted = (await db.execute_fetchall(
                "SELECT COUNT(*) FROM channels WHERE active=1 AND last_post_date=?",
                (today,),
            ))[0][0]
            pending = (await db.execute_fetchall(
                """
                SELECT COUNT(*) FROM channels
                WHERE active=1 AND schedule_date=? AND (last_post_date IS NULL OR last_post_date != ?)
                """,
                (today, today),
            ))[0][0]
        text = await self.get_setting("post_text")
        photo = await self.get_setting("photo_file_id")
        partial = await self.count_partial_today()
        return {
            "total": total,
            "posted_today": posted,
            "pending_today": pending,
            "partial_today": partial,
            "has_text": bool(text and text.strip()),
            "has_photo": bool(photo),
        }

    async def list_active_channels(self) -> list[tuple[int, str, str | None, str]]:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT chat_id, title, username, schedule_minute, last_post_date
                FROM channels
                WHERE active=1
                ORDER BY schedule_minute
                """,
            )
        result = []
        for chat_id, title, username, minute, last_post in rows:
            time_s = self.fmt_minute(minute)
            if last_post == today:
                sched = f"✅ {time_s}"
            else:
                sched = time_s
            result.append((chat_id, title, username, sched))
        return result

    async def next_posts(self, limit: int = 5) -> list[str]:
        today = date.today().isoformat()
        async with aiosqlite.connect(self.path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT title, username, schedule_minute FROM channels
                WHERE active=1 AND schedule_date=? AND (last_post_date IS NULL OR last_post_date != ?)
                ORDER BY schedule_minute LIMIT ?
                """,
                (today, today, limit),
            )
        lines = []
        for title, username, minute in rows:
            h, m = divmod(minute, 60)
            name = f"@{username}" if username else title
            lines.append(f"{name} — {h:02d}:{m:02d}")
        return lines

    @staticmethod
    def fmt_minute(minute: int) -> str:
        h, m = divmod(minute, 60)
        return f"{h:02d}:{m:02d}"

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

TZ_LABEL = os.getenv("TIMEZONE_LABEL", "МСК")


@lru_cache
def _zone() -> ZoneInfo:
    return ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))


def now() -> datetime:
    return datetime.now(_zone())


def today() -> date:
    return now().date()


def today_iso() -> str:
    return today().isoformat()


def now_iso_seconds() -> str:
    return now().strftime("%Y-%m-%d %H:%M:%S")


def now_iso_minutes() -> str:
    return now().strftime("%Y-%m-%d %H:%M")


def fmt_minute(minute: int | None) -> str:
    if minute is None:
        return "—"
    h, m = divmod(minute, 60)
    return f"{h:02d}:{m:02d} {TZ_LABEL}"


def fmt_window(start: str, end: str) -> str:
    return f"{start}–{end} {TZ_LABEL}"


def fmt_clock(ts: str) -> str:
    if len(ts) >= 16 and ts[4] == "-" and ts[10] == " ":
        return f"{ts[11:16]} {TZ_LABEL}"
    return ts


def fmt_user_datetime(value: str | None) -> str:
    if not value:
        return "—"
    text = value.strip()
    if text.endswith(TZ_LABEL):
        return text
    if len(text) >= 16 and text[4] == "-" and text[10] == " ":
        return f"{text[:16]} {TZ_LABEL}"
    return text


def fmt_error_line(text: str) -> str:
    if " · " in text and len(text) > 10 and text[4] == "-":
        ts, rest = text.split(" · ", 1)
        return f"{fmt_user_datetime(ts.strip())} · {rest}"
    return text


def next_midnight_run() -> datetime:
    """00:05 следующего календарного дня по TZ."""
    now_dt = now()
    nxt = (now_dt + timedelta(days=1)).replace(
        hour=0, minute=5, second=0, microsecond=0
    )
    return nxt

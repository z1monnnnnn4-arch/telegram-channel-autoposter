from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Переменная {name} не задана. Скопируйте .env.example в .env")
    return value


def _int_list(value: str) -> list[int]:
    if not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str
    bot_token: str
    admin_ids: list[int]
    post_time: str
    post_delay_sec: float
    max_channels_per_run: int
    content_dir: Path
    photos_per_post: int
    database_path: Path
    session_path: Path

    @classmethod
    def load(cls) -> Settings:
        content_dir = BASE_DIR / os.getenv("CONTENT_DIR", "content")
        db_path = BASE_DIR / os.getenv("DATABASE_PATH", "data/bot.db")
        return cls(
            api_id=int(_require("API_ID")),
            api_hash=_require("API_HASH"),
            phone=_require("PHONE"),
            bot_token=_require("BOT_TOKEN"),
            admin_ids=_int_list(os.getenv("ADMIN_IDS", "")),
            post_time=os.getenv("POST_TIME", "10:00"),
            post_delay_sec=float(os.getenv("POST_DELAY_SEC", "4")),
            max_channels_per_run=int(os.getenv("MAX_CHANNELS_PER_RUN", "0")),
            content_dir=content_dir,
            photos_per_post=int(os.getenv("PHOTOS_PER_POST", "1")),
            database_path=db_path,
            session_path=BASE_DIR / "data" / "user.session",
        )

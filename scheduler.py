from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import Settings
from poster import DailyPoster

logger = logging.getLogger(__name__)


def _parse_post_time(post_time: str) -> tuple[int, int]:
    parts = post_time.strip().split(":")
    if len(parts) != 2:
        raise ValueError("POST_TIME должен быть в формате HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    return hour, minute


class PostScheduler:
    def __init__(self, settings: Settings, poster: DailyPoster) -> None:
        self.settings = settings
        self.poster = poster
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        hour, minute = _parse_post_time(self.settings.post_time)
        self.scheduler.add_job(
            self._daily_job,
            CronTrigger(hour=hour, minute=minute),
            id="daily_post",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Планировщик: ежедневно в %02d:%02d", hour, minute)

    async def _daily_job(self) -> None:
        if self.poster.is_running:
            logger.warning("Пропуск авто-рассылки: уже выполняется")
            return
        logger.info("Авто-рассылка %s", datetime.now().isoformat())
        try:
            await self.poster.run_daily()
        except Exception:
            logger.exception("Ошибка авто-рассылки")

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

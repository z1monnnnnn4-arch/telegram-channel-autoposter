from __future__ import annotations

import asyncio
import logging
import sys

from telethon import TelegramClient

from admin_bot import create_admin_bot
from config import Settings
from content_loader import ContentLoader
from database import Database
from poster import DailyPoster
from scheduler import PostScheduler

logger = logging.getLogger(__name__)


def setup_logging(log_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


async def main() -> None:
    settings = Settings.load()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    setup_logging(str(settings.database_path.parent / "bot.log"))

    db = Database(settings.database_path)
    await db.init()

    content = ContentLoader(settings.content_dir, settings.photos_per_post)

    client = TelegramClient(
        str(settings.session_path),
        settings.api_id,
        settings.api_hash,
    )

    await client.start(phone=settings.phone)
    me = await client.get_me()
    logger.info("Аккаунт: %s (%s)", me.first_name, me.id)

    poster = DailyPoster(settings, db, client, content)
    synced = await poster.sync_channels()
    logger.info("Каналов в базе после sync: %s", synced)

    post_scheduler = PostScheduler(settings, poster)
    post_scheduler.start()

    bot, dp = create_admin_bot(settings, poster)

    try:
        await dp.start_polling(bot)
    finally:
        post_scheduler.shutdown()
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")

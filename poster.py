from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from telethon import TelegramClient
from telethon.errors import (
    ChannelInvalidError,
    ChatAdminRequiredError,
    ChatWriteForbiddenError,
    FloodWaitError,
    RPCError,
)
from telethon.tl.types import Channel as TgChannel

from config import Settings
from content_loader import ContentLoader
from database import Database

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], Awaitable[None]]


class DailyPoster:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        client: TelegramClient,
        content: ContentLoader,
    ) -> None:
        self.settings = settings
        self.db = db
        self.client = client
        self.content = content
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def sync_channels(self) -> int:
        """Подтягивает все каналы, где аккаунт — админ/владелец."""
        count = 0
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            if not isinstance(entity, TgChannel):
                continue
            if not entity.creator and not entity.admin_rights:
                continue
            if entity.megagroup:
                continue

            username = entity.username
            await self.db.upsert_channel(
                channel_id=entity.id,
                title=dialog.title or "",
                username=username,
            )
            count += 1

        logger.info("Синхронизировано каналов: %s", count)
        return count

    async def run_daily(
        self,
        progress: ProgressCallback | None = None,
    ) -> dict[str, int]:
        async with self._lock:
            if self._running:
                raise RuntimeError("Рассылка уже выполняется")
            self._running = True

        run_id = await self.db.start_run()
        limit = self.settings.max_channels_per_run
        channels = await self.db.list_active_channels(limit=limit)

        total = len(channels)
        success = 0
        failed = 0

        logger.info("Старт рассылки: %s каналов", total)

        try:
            for index, channel in enumerate(channels, start=1):
                label = channel.username or channel.title or str(channel.channel_id)
                try:
                    await self._post_to_channel(channel.channel_id)
                    await self.db.mark_post_success(channel.channel_id)
                    success += 1
                    status = "ok"
                except FloodWaitError as exc:
                    wait = exc.seconds + 1
                    logger.warning("FloodWait %ss, пауза...", wait)
                    if progress:
                        await progress(index, total, f"FloodWait {wait}s")
                    await asyncio.sleep(wait)
                    try:
                        await self._post_to_channel(channel.channel_id)
                        await self.db.mark_post_success(channel.channel_id)
                        success += 1
                        status = "ok (retry)"
                    except Exception as retry_exc:
                        await self.db.mark_post_failed(channel.channel_id, str(retry_exc))
                        failed += 1
                        status = f"error: {retry_exc}"
                except (ChatAdminRequiredError, ChatWriteForbiddenError, ChannelInvalidError) as exc:
                    await self.db.deactivate_channel(channel.channel_id, str(exc))
                    await self.db.mark_post_failed(channel.channel_id, str(exc))
                    failed += 1
                    status = f"deactivated: {exc}"
                except RPCError as exc:
                    await self.db.mark_post_failed(channel.channel_id, str(exc))
                    failed += 1
                    status = f"error: {exc}"
                except Exception as exc:
                    await self.db.mark_post_failed(channel.channel_id, str(exc))
                    failed += 1
                    status = f"error: {exc}"
                    logger.exception("Ошибка в канале %s", label)

                if progress:
                    await progress(index, total, f"{label}: {status}")

                if index < total:
                    await asyncio.sleep(self.settings.post_delay_sec)
        finally:
            await self.db.finish_run(run_id, total, success, failed)
            self._running = False

        result = {"total": total, "success": success, "failed": failed}
        logger.info("Рассылка завершена: %s", result)
        return result

    async def _post_to_channel(self, channel_id: int) -> None:
        text, images = self.content.pick_post()
        entity = await self.client.get_entity(channel_id)

        if images:
            if len(images) == 1:
                await self.client.send_file(
                    entity,
                    file=images[0],
                    caption=text or None,
                )
            else:
                await self.client.send_file(
                    entity,
                    file=images,
                    caption=text or None,
                )
        elif text:
            await self.client.send_message(entity, text)
        else:
            raise ValueError(
                "Нет контента: добавьте .txt в content/texts/ или картинки в content/images/"
            )

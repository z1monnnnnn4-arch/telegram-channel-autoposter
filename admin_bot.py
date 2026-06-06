from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from config import Settings
from poster import DailyPoster

logger = logging.getLogger(__name__)


def create_admin_bot(settings: Settings, poster: DailyPoster) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    def is_admin(message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in settings.admin_ids

    @dp.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        if not is_admin(message):
            await message.answer("Нет доступа.")
            return
        await message.answer(
            "Панель управления рассылкой\n\n"
            "/status — статистика\n"
            "/sync — подтянуть каналы из аккаунта\n"
            "/post — запустить рассылку сейчас\n"
            "/help — справка"
        )

    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        if not is_admin(message):
            return
        await message.answer(
            "Бот постит в каналы, где ваш аккаунт — владелец/админ.\n\n"
            "1. Заполните .env\n"
            "2. Положите тексты в content/texts/*.txt\n"
            "3. Картинки в content/images/\n"
            "4. /sync — обновить список каналов\n"
            "5. Рассылка идёт автоматически в POST_TIME\n\n"
            f"Задержка между каналами: {settings.post_delay_sec} сек\n"
            f"Время рассылки: {settings.post_time}"
        )

    @dp.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        if not is_admin(message):
            return
        stats = await poster.db.stats()
        running = "да" if poster.is_running else "нет"
        await message.answer(
            f"Рассылка сейчас: {running}\n"
            f"Каналов всего: {stats['total']}\n"
            f"Активных: {stats['active']}\n"
            f"Постили сегодня: {stats['posted_today']}\n"
            f"Авто-время: {settings.post_time}"
        )

    @dp.message(Command("sync"))
    async def cmd_sync(message: Message) -> None:
        if not is_admin(message):
            return
        if poster.is_running:
            await message.answer("Сначала дождитесь окончания рассылки.")
            return
        await message.answer("Синхронизация каналов...")
        count = await poster.sync_channels()
        stats = await poster.db.stats()
        await message.answer(
            f"Найдено каналов: {count}\n"
            f"В базе активных: {stats['active']}"
        )

    @dp.message(Command("post"))
    async def cmd_post(message: Message) -> None:
        if not is_admin(message):
            return
        if poster.is_running:
            await message.answer("Рассылка уже идёт.")
            return

        status_msg = await message.answer("Запуск рассылки...")

        async def progress(current: int, total: int, info: str) -> None:
            if current % 25 == 0 or current == total:
                try:
                    await status_msg.edit_text(
                        f"Рассылка: {current}/{total}\nПоследний: {info[:200]}"
                    )
                except Exception:
                    pass

        try:
            result = await poster.run_daily(progress=progress)
            await status_msg.edit_text(
                f"Готово\n"
                f"Всего: {result['total']}\n"
                f"Успешно: {result['success']}\n"
                f"Ошибок: {result['failed']}"
            )
        except Exception as exc:
            logger.exception("Ошибка ручной рассылки")
            await status_msg.edit_text(f"Ошибка: {exc}")

    @dp.message(F.text)
    async def ignore_text(message: Message) -> None:
        if is_admin(message):
            await message.answer("Неизвестная команда. /help")

    return bot, dp

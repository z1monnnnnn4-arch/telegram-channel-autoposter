import asyncio
import html
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psutil
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatMemberUpdated, InputMediaPhoto, Message
from dotenv import load_dotenv

import ui
from db import DB
from runtime import SingleInstance, backup_database

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {int(x) for x in os.environ["ADMIN_IDS"].split(",") if x.strip()}
WINDOW_START = os.getenv("POST_WINDOW_START", "08:00")
WINDOW_END = os.getenv("POST_WINDOW_END", "22:00")
WINDOW = f"{WINDOW_START}–{WINDOW_END}"
CHANNEL_DELAY = float(os.getenv("CHANNEL_DELAY_SEC", "4"))
DB_PATH = Path(os.getenv("DB_PATH", "data/bot.db"))
ROOT = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("bot")

router = Router()
db = DB(DB_PATH, WINDOW_START, WINDOW_END)
_post_lock = asyncio.Lock()
_wait: dict[int, str] = {}
_extra_admins: set[int] = set()
_started_at = datetime.now()
POST_ATTEMPTS = 3
POST_BACKOFF = (2, 5, 10)
ALERT_COOLDOWN_SEC = 300
_instance: SingleInstance | None = None
_alert_at: datetime | None = None


async def refresh_admins() -> None:
    global _extra_admins
    _extra_admins = set(await db.get_extra_admins())


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and (user_id in ADMIN_IDS or user_id in _extra_admins)


def is_owner(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_IDS


def format_uptime() -> str:
    sec = int((datetime.now() - _started_at).total_seconds())
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} ч {m} мин"
    if m:
        return f"{m} мин {s} сек"
    return f"{s} сек"


async def all_admin_ids() -> list[int]:
    return sorted(ADMIN_IDS | _extra_admins)


def get_system_load() -> dict[str, str]:
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(ROOT))
    return {
        "cpu": f"{cpu:.0f}%",
        "ram": f"{mem.percent:.0f}% ({mem.used // (1024 ** 2)} / {mem.total // (1024 ** 2)} MB)",
        "disk": f"{disk.percent:.0f}% ({disk.free // (1024 ** 3)} GB свободно)",
    }


async def git_pull() -> tuple[bool, str]:
    def run() -> tuple[bool, str]:
        if not (ROOT / ".git").exists():
            return False, "Git-репозиторий не найден"
        try:
            r = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            return False, "git не установлен"
        out = (r.stdout + r.stderr).strip() or "готово"
        return r.returncode == 0, out[:800]

    return await asyncio.to_thread(run)


def cancel_wait(user_id: int) -> None:
    _wait.pop(user_id, None)


def channel_label(title: str, username: str | None) -> str:
    return f"@{username}" if username else title


def parse_channel_ref(text: str) -> str | int | None:
    text = text.strip()
    if text.startswith("@"):
        return text
    if "t.me/" in text:
        part = text.split("t.me/")[-1].split("/")[0].split("?")[0]
        return f"@{part}" if part else None
    if text.lstrip("-").isdigit():
        return int(text)
    return None


async def schedule_restart(delay: float = 1.5) -> None:
    await asyncio.sleep(delay)
    os.execv(sys.executable, [sys.executable, str(ROOT / "main.py")])


async def register_channel(bot: Bot, ref: str | int) -> tuple[bool, str]:
    try:
        chat = await bot.get_chat(ref)
    except Exception as ex:
        return False, f"Канал не найден: {ex}"
    if chat.type != ChatType.CHANNEL:
        return False, "Это не канал"
    me = await bot.me()
    try:
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception:
        return False, "Бот не видит канал — добавьте админом"
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return False, "Бот не админ — нужно «Управление публикациями»"
    await db.upsert_channel(chat.id, chat.title or "", chat.username)
    return True, channel_label(chat.title or "", chat.username)


async def send_menu(message: Message, *, edit: bool = False) -> None:
    body = await build_dashboard()
    markup = ui.inline_menu()
    if edit:
        await message.edit_text(body, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await message.answer(body, reply_markup=markup, parse_mode=ParseMode.HTML)


async def edit_screen(
    q: CallbackQuery,
    text: str,
    reply_markup=None,
    *,
    parse_mode: ParseMode = ParseMode.HTML,
) -> None:
    msg = q.message
    if msg.photo or msg.document or msg.video or msg.animation:
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
        await q.bot.send_message(
            msg.chat.id, text, reply_markup=reply_markup, parse_mode=parse_mode
        )
        return
    try:
        await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as ex:
        err = str(ex).lower()
        if "message is not modified" in err:
            return
        if "no text" in err or "can't be edited" in err:
            await q.bot.send_message(
                msg.chat.id, text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            return
        raise


async def deny(msg: Message) -> None:
    await msg.answer(
        ui.page("🔒", "Нет доступа", "СИСТЕМА", "Этот бот только для администратора."),
        parse_mode=ParseMode.HTML,
    )


async def build_dashboard() -> str:
    s = await db.stats()
    lines = await db.next_posts(5)
    return ui.dashboard(s, lines, WINDOW)


async def build_stats() -> str:
    s = await db.stats()
    lines = await db.next_posts(10)
    inactive = await db.count_inactive()
    return ui.stats_page(s, lines, inactive, WINDOW)


async def show_channels(q: CallbackQuery, page: int = 0) -> None:
    channels = await db.list_active_channels()
    total = len(channels)
    await q.message.edit_text(
        ui.channels_list(channels, page, total),
        reply_markup=ui.inline_channels_picker(channels, page, total),
        parse_mode=ParseMode.HTML,
    )


async def show_channel_detail(q: CallbackQuery, chat_id: int) -> None:
    ch = await db.get_channel(chat_id)
    if not ch:
        await q.answer("Канал не найден", show_alert=True)
        return
    title, username, minute, sched_date, last_post, active, partial_date = ch
    name = channel_label(title, username)
    today = datetime.now().date().isoformat()
    partial = partial_date == today and last_post != today
    await q.message.edit_text(
        ui.channel_detail(
            name,
            db.fmt_minute(minute),
            sched_date or "—",
            last_post == today,
            bool(active),
            partial,
        ),
        reply_markup=ui.inline_channel_detail(chat_id),
        parse_mode=ParseMode.HTML,
    )


async def show_logs(q: CallbackQuery) -> None:
    last = await db.get_last_error()
    errors = await db.recent_errors(10)
    if last:
        last = html.escape(last)
    errors = [(t, html.escape(n), html.escape(d or "")) for t, n, d in errors]
    await q.message.edit_text(
        ui.logs_page(last, errors),
        reply_markup=ui.inline_logs(),
        parse_mode=ParseMode.HTML,
    )


async def alert_admins(bot: Bot, detail: str) -> None:
    global _alert_at
    now = datetime.now()
    if _alert_at and (now - _alert_at).total_seconds() < ALERT_COOLDOWN_SEC:
        return
    _alert_at = now
    body = html.escape(detail[:500])
    for aid in await all_admin_ids():
        try:
            await bot.send_message(
                aid,
                ui.page("⚠️", "Системная ошибка", "СИСТЕМА", body),
                reply_markup=ui.inline_open_menu(),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def tg_retry(coro_factory):
    last: Exception | None = None
    for attempt in range(POST_ATTEMPTS):
        try:
            return await coro_factory()
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            last = e
        except (TelegramNetworkError, TelegramServerError) as e:
            last = e
            if attempt + 1 < POST_ATTEMPTS:
                await asyncio.sleep(POST_BACKOFF[min(attempt, len(POST_BACKOFF) - 1)])
        except Exception:
            raise
    if last:
        raise last
    raise RuntimeError("retry exhausted")


async def post_one(
    bot: Bot,
    chat_id: int,
    text: str,
    photo: str,
    *,
    text_only: bool = False,
) -> None:
    if not text_only:
        await tg_retry(lambda: bot.send_photo(chat_id, photo))
        await db.set_partial(chat_id)
        await asyncio.sleep(1.5)
    await tg_retry(lambda: bot.send_message(chat_id, text))


async def show_menu(msg: Message) -> None:
    await send_menu(msg)


async def post_list(
    bot: Bot,
    channels: list[tuple[int, str, str | None]],
    text: str,
    photo: str,
    *,
    source: str = "auto",
) -> tuple[int, int]:
    ok = fail = 0
    for i, (chat_id, title, username) in enumerate(channels):
        name = channel_label(title, username) or str(chat_id)
        text_only = await db.needs_text_only(chat_id)
        try:
            await post_one(bot, chat_id, text, photo, text_only=text_only)
            await db.mark_posted(chat_id)
            note = "дотекст" if text_only else ""
            await db.log_post(chat_id, name, "ok", note, source=source)
            ok += 1
            log.info("posted %s%s", name, " (text only)" if text_only else "")
        except TelegramForbiddenError:
            fail += 1
            await db.deactivate(chat_id)
            await db.log_post(chat_id, name, "off", "нет прав", source)
            log.warning("deactivated %s", name)
        except Exception as ex:
            fail += 1
            msg = str(ex)
            if await db.needs_text_only(chat_id):
                await db.log_post(chat_id, name, "partial", msg, source)
                log.warning("partial %s: %s", name, ex)
                await alert_admins(bot, f"Частичный пост {name}: фото есть, текст не ушёл — {ex}")
            else:
                await db.log_post(chat_id, name, "fail", msg, source)
                log.warning("fail %s: %s", name, ex)
        if i + 1 < len(channels):
            await asyncio.sleep(CHANNEL_DELAY)
    return ok, fail


async def run_due_posts(bot: Bot) -> tuple[int, int]:
    text = await db.get_setting("post_text")
    photo = await db.get_setting("photo_file_id")
    if not text or not photo:
        return 0, 0
    due = await db.due_channels()
    if not due:
        return 0, 0
    async with _post_lock:
        return await post_list(bot, due, text, photo, source="auto")


async def do_send(bot: Bot) -> tuple[int, int, str | None]:
    text = await db.get_setting("post_text")
    photo = await db.get_setting("photo_file_id")
    if not text or not photo:
        return 0, 0, "Сначала задайте 📝 текст и 🖼 фото."
    pending = await db.pending_channels()
    if not pending:
        return 0, 0, "Все каналы уже получили пост сегодня."
    async with _post_lock:
        ok, fail = await post_list(bot, pending, text, photo, source="bulk")
    return ok, fail, None


async def do_send_one(bot: Bot, chat_id: int) -> tuple[bool, str | None]:
    text = await db.get_setting("post_text")
    photo = await db.get_setting("photo_file_id")
    if not text or not photo:
        return False, "Сначала задайте 📝 текст и 🖼 фото."
    ch = await db.get_channel(chat_id)
    if not ch:
        return False, "Канал не найден в базе."
    title, username, *_ = ch
    async with _post_lock:
        ok, fail = await post_list(
            bot, [(chat_id, title, username)], text, photo, source="manual"
        )
    if ok:
        return True, None
    return False, "Не удалось отправить — см. 📜 Логи"


async def process_manual_channel(msg: Message) -> None:
    ref: str | int | None = None
    if msg.text:
        ref = parse_channel_ref(msg.text)
    if not ref and msg.forward_origin:
        chat = getattr(msg.forward_origin, "chat", None)
        if chat:
            ref = chat.id
    if not ref:
        await msg.answer(
            ui.page("❌", "Не понял", "КАНАЛЫ", "Отправьте @channel, t.me/… или пересылку из канала."),
            reply_markup=ui.inline_back(ui.CB_ADD_CHANNEL),
            parse_mode=ParseMode.HTML,
        )
        return
    ok, result = await register_channel(msg.bot, ref)
    if ok:
        await msg.answer(
            ui.page("✅", "Канал добавлен", "КАНАЛЫ", f"<b>{result}</b> в базе."),
            reply_markup=ui.inline_back(ui.CB_CHANNELS),
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.answer(
            ui.page("❌", "Ошибка", "КАНАЛЫ", result),
            reply_markup=ui.inline_back(ui.CB_ADD_CHANNEL),
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("start"))
async def cmd_start(msg: Message) -> None:
    if not is_admin(msg.from_user.id if msg.from_user else None):
        await deny(msg)
        return
    if msg.from_user:
        cancel_wait(msg.from_user.id)
    await show_menu(msg)


@router.message(F.text.regexp(r"^/\w"))
async def unknown_command(msg: Message) -> None:
    if not is_admin(msg.from_user.id if msg.from_user else None):
        return
    if (msg.text or "").startswith("/start"):
        return
    await msg.answer(
        ui.page("ℹ️", "Подсказка", "ГЛАВНАЯ", "Все действия — через кнопки меню."),
        reply_markup=ui.inline_open_menu(),
        parse_mode=ParseMode.HTML,
    )


@router.message(F.photo)
async def on_photo(msg: Message) -> None:
    if not is_admin(msg.from_user.id if msg.from_user else None):
        return
    if _wait.get(msg.from_user.id) == "photo":
        _wait.pop(msg.from_user.id, None)
        await db.set_setting("photo_file_id", msg.photo[-1].file_id)
        await msg.answer(
            ui.page("✅", "Картинка сохранена", "КОНТЕНТ", "Контент обновлён для всех каналов."),
            reply_markup=ui.inline_back(),
            parse_mode=ParseMode.HTML,
        )


def _resolve_admin_target(msg: Message) -> int | None:
    if msg.text and msg.text.strip().lstrip("-").isdigit():
        return int(msg.text.strip())
    if msg.forward_origin and getattr(msg.forward_origin, "sender_user", None):
        return msg.forward_origin.sender_user.id
    return None


async def _process_admin_add(msg: Message) -> None:
    target_id = _resolve_admin_target(msg)
    if not target_id:
        await msg.answer(
            ui.page("❌", "Не удалось", "СИСТЕМА", "Отправьте ID числом или перешлите сообщение."),
            reply_markup=ui.inline_back(ui.CB_ADMINS),
            parse_mode=ParseMode.HTML,
        )
        return
    if target_id in ADMIN_IDS or target_id in _extra_admins:
        await msg.answer(
            ui.page("ℹ️", "Уже есть доступ", "СИСТЕМА", f"Пользователь <code>{target_id}</code> уже админ."),
            reply_markup=ui.inline_back(ui.CB_ADMINS),
            parse_mode=ParseMode.HTML,
        )
        return
    await db.add_extra_admin(target_id)
    await refresh_admins()
    await msg.answer(
        ui.page("✅", "Админ добавлен", "СИСТЕМА", f"Доступ выдан: <code>{target_id}</code>"),
        reply_markup=ui.inline_back(ui.CB_ADMINS),
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text)
async def on_text(msg: Message) -> None:
    if not is_admin(msg.from_user.id if msg.from_user else None):
        return
    if not msg.text or msg.text.startswith("/"):
        return
    wait = _wait.get(msg.from_user.id)
    if wait == "text":
        _wait.pop(msg.from_user.id, None)
        await db.set_setting("post_text", msg.text.strip())
        await msg.answer(
            ui.page("✅", "Текст сохранён", "КОНТЕНТ", "Контент обновлён для всех каналов."),
            reply_markup=ui.inline_back(),
            parse_mode=ParseMode.HTML,
        )
        return
    if wait == "admin":
        if not is_owner(msg.from_user.id):
            return
        _wait.pop(msg.from_user.id, None)
        await _process_admin_add(msg)
        return
    if wait == "add_channel":
        _wait.pop(msg.from_user.id, None)
        await process_manual_channel(msg)


@router.message(F.forward_origin)
async def on_forward(msg: Message) -> None:
    if not is_admin(msg.from_user.id if msg.from_user else None):
        return
    wait = _wait.get(msg.from_user.id)
    if wait == "admin" and is_owner(msg.from_user.id):
        _wait.pop(msg.from_user.id, None)
        await _process_admin_add(msg)
        return
    if wait == "add_channel":
        _wait.pop(msg.from_user.id, None)
        await process_manual_channel(msg)


@router.callback_query(F.data == ui.CB_NOOP)
async def cb_noop(q: CallbackQuery) -> None:
    await q.answer()


@router.callback_query(F.data == ui.CB_MENU)
async def cb_menu(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    cancel_wait(q.from_user.id)
    await q.answer()
    await edit_screen(
        q,
        await build_dashboard(),
        ui.inline_menu(),
    )


@router.callback_query(F.data == ui.CB_STATUS)
async def cb_status(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        await build_stats(),
        reply_markup=ui.inline_back(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_HELP)
async def cb_help(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        ui.help_text(WINDOW),
        reply_markup=ui.inline_back(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_SETTEXT)
async def cb_settext(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    _wait[q.from_user.id] = "text"
    await q.answer()
    await q.message.edit_text(
        ui.settext_prompt(),
        reply_markup=ui.inline_wait_input(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_SETPHOTO)
async def cb_setphoto(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    _wait[q.from_user.id] = "photo"
    await q.answer()
    await q.message.edit_text(
        ui.setphoto_prompt(),
        reply_markup=ui.inline_wait_input(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_SEND)
async def cb_send(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    pending = await db.pending_channels()
    await q.answer()
    await q.message.edit_text(
        ui.send_confirm(len(pending)),
        reply_markup=ui.inline_confirm_send(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_SEND_YES)
async def cb_send_yes(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer("Отправляю…")
    ok, fail, err = await do_send(q.bot)
    if err:
        await q.message.edit_text(
            ui.page("❌", "Отправка", "РАССЫЛКА", err),
            reply_markup=ui.inline_back(),
            parse_mode=ParseMode.HTML,
        )
    else:
        await q.message.edit_text(
            ui.page("✅", "Отправка завершена", "РАССЫЛКА", f"Успешно: <b>{ok}</b>\nОшибок: <b>{fail}</b>"),
            reply_markup=ui.inline_back(),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data == ui.CB_CHANNELS)
async def cb_channels(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await show_channels(q, 0)


@router.callback_query(F.data.startswith(ui.CB_CHANNELS_PAGE_PREFIX))
async def cb_channels_page(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    page = int(q.data.removeprefix(ui.CB_CHANNELS_PAGE_PREFIX))
    await q.answer()
    await show_channels(q, page)


@router.callback_query(F.data.startswith(ui.CB_CHANNEL_PREFIX))
async def cb_channel_detail(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    chat_id = int(q.data.removeprefix(ui.CB_CHANNEL_PREFIX))
    await q.answer()
    await show_channel_detail(q, chat_id)


@router.callback_query(F.data.startswith(ui.CB_SEND_ONE_PREFIX))
async def cb_send_one(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    chat_id = int(q.data.removeprefix(ui.CB_SEND_ONE_PREFIX))
    ch = await db.get_channel(chat_id)
    if not ch:
        await q.answer("Канал не найден", show_alert=True)
        return
    name = channel_label(ch[0], ch[1])
    await q.answer()
    await q.message.edit_text(
        ui.send_one_confirm(name),
        reply_markup=ui.inline_confirm_send_one(chat_id),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith(ui.CB_SEND_ONE_YES_PREFIX))
async def cb_send_one_yes(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    chat_id = int(q.data.removeprefix(ui.CB_SEND_ONE_YES_PREFIX))
    await q.answer("Отправляю…")
    ok, err = await do_send_one(q.bot, chat_id)
    if err:
        await q.message.edit_text(
            ui.page("❌", "Отправка", "КАНАЛЫ", err),
            reply_markup=ui.inline_back(ui.CB_CHANNELS),
            parse_mode=ParseMode.HTML,
        )
    else:
        await q.message.edit_text(
            ui.page("✅", "Отправлено", "КАНАЛЫ", "Пост опубликован в канале."),
            reply_markup=ui.inline_back(f"{ui.CB_CHANNEL_PREFIX}{chat_id}"),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data.startswith(ui.CB_SCHEDULE_ONE_PREFIX))
async def cb_schedule_one(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    chat_id = int(q.data.removeprefix(ui.CB_SCHEDULE_ONE_PREFIX))
    if await db.regenerate_channel(chat_id):
        ch = await db.get_channel(chat_id)
        time_s = db.fmt_minute(ch[2]) if ch else "—"
        await q.answer(f"Новое время: {time_s}")
    else:
        await q.answer("Канал не найден", show_alert=True)
        return
    await show_channel_detail(q, chat_id)


@router.callback_query(F.data.startswith(ui.CB_REMOVE_PREFIX))
async def cb_remove_channel(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    chat_id = int(q.data.removeprefix(ui.CB_REMOVE_PREFIX))
    ch = await db.get_channel(chat_id)
    if not ch:
        await q.answer("Канал не найден", show_alert=True)
        return
    name = channel_label(ch[0], ch[1])
    await q.answer()
    await q.message.edit_text(
        ui.remove_confirm(name),
        reply_markup=ui.inline_confirm_remove(chat_id),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith(ui.CB_REMOVE_YES_PREFIX))
async def cb_remove_yes(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    chat_id = int(q.data.removeprefix(ui.CB_REMOVE_YES_PREFIX))
    await db.delete_channel(chat_id)
    await q.answer("Удалён")
    await show_channels(q, 0)


@router.callback_query(F.data == ui.CB_CLEAR)
async def cb_clear(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        ui.clear_menu(),
        reply_markup=ui.inline_clear(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_CLEAR_INACTIVE)
async def cb_clear_inactive(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    n = await db.clear_inactive()
    await q.answer(f"Удалено: {n}")
    await q.message.edit_text(
        ui.page("🧹", "Очистка выполнена", "КАНАЛЫ", f"Удалено неактивных: <b>{n}</b>"),
        reply_markup=ui.inline_back(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_CLEAR_ALL)
async def cb_clear_all(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        ui.page("⚠️", "Удалить все каналы", "КАНАЛЫ", "Удалить <b>все</b> каналы из базы?\nТекст и фото сохранятся."),
        reply_markup=ui.inline_confirm_clear_all(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_CLEAR_YES)
async def cb_clear_yes(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    n = await db.clear_all()
    await q.answer("Готово")
    await q.message.edit_text(
        ui.page("✅", "Очистка выполнена", "КАНАЛЫ", f"Удалено каналов: <b>{n}</b>"),
        reply_markup=ui.inline_back(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_PREVIEW)
async def cb_preview(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    text = await db.get_setting("post_text")
    s = await db.stats()
    photo = await db.get_setting("photo_file_id")
    body = ui.content_preview(text, s["has_photo"])
    await q.answer()
    if photo:
        if q.message.photo:
            await q.message.edit_media(
                InputMediaPhoto(media=photo, caption=body, parse_mode=ParseMode.HTML),
                reply_markup=ui.inline_back(),
            )
        else:
            try:
                await q.message.delete()
            except TelegramBadRequest:
                pass
            await q.bot.send_photo(
                q.message.chat.id,
                photo,
                caption=body,
                reply_markup=ui.inline_back(),
                parse_mode=ParseMode.HTML,
            )
    else:
        await edit_screen(q, body, ui.inline_back())


@router.callback_query(F.data == ui.CB_REGEN)
async def cb_regen(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    s = await db.stats()
    await q.answer()
    await q.message.edit_text(
        ui.regen_confirm(s["total"]),
        reply_markup=ui.inline_confirm_regen(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_REGEN_YES)
async def cb_regen_yes(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    count = await db.regenerate_day()
    await q.answer("Готово")
    await q.message.edit_text(
        ui.page("✅", "Расписание обновлено", "РАССЫЛКА", f"Новое время для <b>{count}</b> каналов."),
        reply_markup=ui.inline_back(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_ADD_CHANNEL)
async def cb_add_channel(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        ui.add_channel_help(),
        reply_markup=ui.inline_add_channel(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_ADD_MANUAL)
async def cb_add_manual(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    _wait[q.from_user.id] = "add_channel"
    await q.answer()
    await q.message.edit_text(
        ui.add_channel_manual_prompt(),
        reply_markup=ui.inline_wait_input(ui.CB_ADD_CHANNEL),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_LOGS)
async def cb_logs(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await q.answer()
    await show_logs(q)


@router.callback_query(F.data == ui.CB_LOGS_CLEAR)
async def cb_logs_clear(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    await db.clear_last_error()
    await q.answer("Сброшено")
    await show_logs(q)


@router.callback_query(F.data == ui.CB_SYS)
async def cb_sys(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    s = await db.stats()
    load = await asyncio.to_thread(get_system_load)
    last_backup = await db.get_setting("last_backup")
    last_ok = await db.get_setting("last_ok")
    await q.answer()
    await q.message.edit_text(
        ui.sys_page(
            ui.BOT_VERSION,
            WINDOW,
            CHANNEL_DELAY,
            format_uptime(),
            s,
            load,
            last_backup,
            last_ok,
        ),
        reply_markup=ui.inline_back(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_RELOAD)
async def cb_reload(q: CallbackQuery) -> None:
    if not is_owner(q.from_user.id):
        await q.answer("Только владелец из .env", show_alert=True)
        return
    await q.answer()
    await q.message.edit_text(
        ui.reload_prompt(),
        reply_markup=ui.inline_confirm_restart(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_RESTART_YES)
async def cb_restart_yes(q: CallbackQuery) -> None:
    if not is_owner(q.from_user.id):
        await q.answer("Только владелец из .env", show_alert=True)
        return
    cancel_wait(q.from_user.id)
    await refresh_admins()
    await db.ensure_today_schedules()
    await q.answer("Перезапуск…")
    await q.message.edit_text(ui.reload_done(), parse_mode=ParseMode.HTML)
    asyncio.create_task(schedule_restart())


@router.callback_query(F.data == ui.CB_UPDATE)
async def cb_update(q: CallbackQuery) -> None:
    if not is_owner(q.from_user.id):
        await q.answer("Только владелец из .env", show_alert=True)
        return
    await q.answer("Проверяю…")
    ok, output = await git_pull()
    markup = ui.inline_after_update() if ok else ui.inline_back()
    await q.message.edit_text(
        ui.update_result(ok, html.escape(output)),
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_UPDATE_RESTART)
async def cb_update_restart(q: CallbackQuery) -> None:
    await cb_restart_yes(q)


@router.callback_query(F.data == ui.CB_ADMINS)
async def cb_admins(q: CallbackQuery) -> None:
    if not is_admin(q.from_user.id):
        await q.answer("Нет доступа", show_alert=True)
        return
    extra = await db.get_extra_admins()
    await q.answer()
    await q.message.edit_text(
        ui.admins_page(await all_admin_ids(), ADMIN_IDS, extra),
        reply_markup=ui.inline_admins(extra),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == ui.CB_ADMIN_ADD)
async def cb_admin_add(q: CallbackQuery) -> None:
    if not is_owner(q.from_user.id):
        await q.answer("Только владелец из .env", show_alert=True)
        return
    _wait[q.from_user.id] = "admin"
    await q.answer()
    await q.message.edit_text(
        ui.admin_add_prompt(),
        reply_markup=ui.inline_wait_input(ui.CB_ADMINS),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith(ui.CB_ADMIN_REMOVE_PREFIX))
async def cb_admin_remove(q: CallbackQuery) -> None:
    if not is_owner(q.from_user.id):
        await q.answer("Только владелец из .env", show_alert=True)
        return
    uid = int(q.data.removeprefix(ui.CB_ADMIN_REMOVE_PREFIX))
    if uid in ADMIN_IDS:
        await q.answer("Нельзя убрать владельца", show_alert=True)
        return
    removed = await db.remove_extra_admin(uid)
    await refresh_admins()
    await q.answer("Убран" if removed else "Не найден")
    extra = await db.get_extra_admins()
    await q.message.edit_text(
        ui.admins_page(await all_admin_ids(), ADMIN_IDS, extra),
        reply_markup=ui.inline_admins(extra),
        parse_mode=ParseMode.HTML,
    )


@router.my_chat_member()
async def bot_member_update(event: ChatMemberUpdated) -> None:
    if event.chat.type != ChatType.CHANNEL:
        return
    status = event.new_chat_member.status
    if status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        await db.upsert_channel(
            event.chat.id,
            event.chat.title or "",
            event.chat.username,
        )
        log.info("added %s", event.chat.title)
        name = channel_label(event.chat.title or "", event.chat.username)
        for aid in await all_admin_ids():
            try:
                await event.bot.send_message(
                    aid,
                    ui.page("📡", "Канал добавлен", "КАНАЛЫ", f"<b>{name}</b>\nРасписание назначено."),
                    reply_markup=ui.inline_open_menu(),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
    else:
        await db.deactivate(event.chat.id)
        name = channel_label(event.chat.title or "", event.chat.username)
        await db.log_post(event.chat.id, name, "off", "бот снят с админов", "auto")
        log.info("removed %s", event.chat.title)


async def poster_loop(bot: Bot) -> None:
    while True:
        try:
            await run_due_posts(bot)
        except Exception as ex:
            log.exception("poster_loop")
            await db.set_last_error(f"система: {ex}")
            await alert_admins(bot, f"Ошибка цикла постинга: {ex}")
        await asyncio.sleep(60)


async def midnight_loop(bot: Bot) -> None:
    while True:
        now = datetime.now()
        nxt = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
        await asyncio.sleep((nxt - now).total_seconds())
        backup_name = await asyncio.to_thread(backup_database, DB_PATH)
        if backup_name:
            await db.set_setting(
                "last_backup", datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            log.info("backup %s", backup_name)
        count = await db.regenerate_day()
        log.info("schedules reset: %s", count)
        for aid in await all_admin_ids():
            try:
                await bot.send_message(
                    aid,
                    ui.page("🌅", "Новый день", "РАССЫЛКА", f"Расписание обновлено для <b>{count}</b> каналов."),
                    reply_markup=ui.inline_open_menu(),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass


async def maybe_backup() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    last = await db.get_setting("last_backup")
    if last and last.startswith(today):
        return
    backup_name = await asyncio.to_thread(backup_database, DB_PATH)
    if backup_name:
        await db.set_setting("last_backup", datetime.now().strftime("%Y-%m-%d %H:%M"))
        log.info("backup %s", backup_name)


async def main() -> None:
    global _instance
    _instance = SingleInstance(DB_PATH.parent / "bot.lock")
    _instance.acquire()
    try:
        await db.init()
        await refresh_admins()
        await db.ensure_today_schedules()
        await maybe_backup()

        bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            await bot.set_my_commands(ui.BOT_COMMANDS)
        except Exception as ex:
            log.warning("set_my_commands skipped: %s", ex)

        dp = Dispatcher()
        dp.include_router(router)
        asyncio.create_task(poster_loop(bot))
        asyncio.create_task(midnight_loop(bot))
        log.info("started v%s", ui.BOT_VERSION)
        await dp.start_polling(bot)
    finally:
        if _instance:
            _instance.release()


if __name__ == "__main__":
    import time

    while True:
        try:
            asyncio.run(main())
            break
        except KeyboardInterrupt:
            log.info("stopped")
            break
        except Exception:
            log.exception("bot crashed, restart in 3s")
            time.sleep(3)

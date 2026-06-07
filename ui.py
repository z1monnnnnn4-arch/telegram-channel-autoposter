from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
]

CB_MENU = "menu"
CB_STATUS = "status"
CB_SETTEXT = "settext"
CB_SETPHOTO = "setphoto"
CB_SEND = "send"
CB_SEND_YES = "send_yes"
CB_CLEAR = "clear"
CB_CLEAR_INACTIVE = "clear_inactive"
CB_CLEAR_ALL = "clear_all"
CB_CLEAR_YES = "clear_yes"
CB_HELP = "help"
CB_CHANNELS = "channels"
CB_PREVIEW = "preview"
CB_REGEN = "regen"
CB_REGEN_YES = "regen_yes"
CB_ADD_CHANNEL = "add_channel"
CB_ADD_MANUAL = "add_manual"
CB_SYS = "sys"
CB_RELOAD = "reload"
CB_RESTART_YES = "restart_yes"
CB_UPDATE = "update"
CB_UPDATE_RESTART = "update_restart"
CB_ADMINS = "admins"
CB_ADMIN_ADD = "admin_add"
CB_LOGS = "logs"
CB_LOGS_CLEAR = "logs_clear"
CB_REMOVE_PREFIX = "rm:"
CB_CHANNEL_PREFIX = "ch:"
CB_CHANNELS_PAGE_PREFIX = "chpg:"
CB_SEND_ONE_PREFIX = "snd:"
CB_SEND_ONE_YES_PREFIX = "sndy:"
CB_SCHEDULE_ONE_PREFIX = "sch:"
CB_REMOVE_YES_PREFIX = "rmy:"
CB_ADMIN_REMOVE_PREFIX = "admrm:"
CB_NOOP = "noop"

BOT_VERSION = "1.2"
CHANNELS_PER_PAGE = 12


def page(icon: str, title: str, section: str, body: str = "") -> str:
    text = f"{icon} <b>{title}</b>\n<i>Раздел: {section}</i>"
    if body:
        text += f"\n\n{body}"
    return text


def _section(title: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=f"——— {title} ———", callback_data=CB_NOOP)


def inline_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("КОНТЕНТ")],
            [
                InlineKeyboardButton(text="📝 Текст", callback_data=CB_SETTEXT),
                InlineKeyboardButton(text="🖼 Фото", callback_data=CB_SETPHOTO),
            ],
            [InlineKeyboardButton(text="👁 Просмотр контента", callback_data=CB_PREVIEW)],
            [_section("РАССЫЛКА")],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data=CB_STATUS),
                InlineKeyboardButton(text="🚀 Отправить", callback_data=CB_SEND),
            ],
            [InlineKeyboardButton(text="🔄 Перегенерировать расписание", callback_data=CB_REGEN)],
            [_section("КАНАЛЫ")],
            [
                InlineKeyboardButton(text="📋 Список", callback_data=CB_CHANNELS),
                InlineKeyboardButton(text="➕ Подключить", callback_data=CB_ADD_CHANNEL),
            ],
            [InlineKeyboardButton(text="🗑 Очистка", callback_data=CB_CLEAR)],
            [_section("СИСТЕМА")],
            [
                InlineKeyboardButton(text="💻 Нагрузка", callback_data=CB_SYS),
                InlineKeyboardButton(text="📜 Логи", callback_data=CB_LOGS),
            ],
            [
                InlineKeyboardButton(text="🔑 Админы", callback_data=CB_ADMINS),
                InlineKeyboardButton(text="🔄 Перезагрузка", callback_data=CB_RELOAD),
            ],
            [InlineKeyboardButton(text="⬆️ Обновление", callback_data=CB_UPDATE)],
            [_section("ПРОЧЕЕ")],
            [InlineKeyboardButton(text="❓ Справка", callback_data=CB_HELP)],
        ]
    )


def inline_back(to: str = CB_MENU) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=to)]]
    )


def inline_open_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Меню", callback_data=CB_MENU)]]
    )


def inline_clear() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ОЧИСТКА")],
            [
                InlineKeyboardButton(text="🧹 Неактивные", callback_data=CB_CLEAR_INACTIVE),
                InlineKeyboardButton(text="⚠️ Все каналы", callback_data=CB_CLEAR_ALL),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def inline_wait_input(back: str = CB_MENU) -> InlineKeyboardMarkup:
    return inline_back(back)


def inline_confirm_send() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ПОДТВЕРЖДЕНИЕ")],
            [InlineKeyboardButton(text="✅ Да, отправить", callback_data=CB_SEND_YES)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def inline_confirm_regen() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ПОДТВЕРЖДЕНИЕ")],
            [InlineKeyboardButton(text="✅ Да, перегенерировать", callback_data=CB_REGEN_YES)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def inline_confirm_restart() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ПОДТВЕРЖДЕНИЕ")],
            [InlineKeyboardButton(text="✅ Перезапустить процесс", callback_data=CB_RESTART_YES)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def inline_confirm_clear_all() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ПОДТВЕРЖДЕНИЕ")],
            [InlineKeyboardButton(text="✅ Удалить все", callback_data=CB_CLEAR_YES)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_CLEAR)],
        ]
    )


def inline_add_channel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Добавить вручную", callback_data=CB_ADD_MANUAL)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def inline_channels_picker(
    channels: list[tuple[int, str, str | None, str]],
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[_section("КАНАЛЫ")]]
    start = page * CHANNELS_PER_PAGE
    chunk = channels[start : start + CHANNELS_PER_PAGE]
    for chat_id, title, username, sched in chunk:
        name = f"@{username}" if username else (title[:22] + "…" if len(title) > 22 else title)
        rows.append([
            InlineKeyboardButton(
                text=f"📡 {name} · {sched}",
                callback_data=f"{CB_CHANNEL_PREFIX}{chat_id}",
            )
        ])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{CB_CHANNELS_PAGE_PREFIX}{page - 1}"))
    if (page + 1) * CHANNELS_PER_PAGE < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{CB_CHANNELS_PAGE_PREFIX}{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inline_channel_detail(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("КАНАЛ")],
            [InlineKeyboardButton(text="🚀 Отправить сейчас", callback_data=f"{CB_SEND_ONE_PREFIX}{chat_id}")],
            [InlineKeyboardButton(text="🔄 Новое время", callback_data=f"{CB_SCHEDULE_ONE_PREFIX}{chat_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"{CB_REMOVE_PREFIX}{chat_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data=CB_CHANNELS)],
        ]
    )


def inline_confirm_send_one(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ПОДТВЕРЖДЕНИЕ")],
            [InlineKeyboardButton(text="✅ Да, отправить", callback_data=f"{CB_SEND_ONE_YES_PREFIX}{chat_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"{CB_CHANNEL_PREFIX}{chat_id}")],
        ]
    )


def inline_confirm_remove(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_section("ПОДТВЕРЖДЕНИЕ")],
            [InlineKeyboardButton(text="✅ Удалить из базы", callback_data=f"{CB_REMOVE_YES_PREFIX}{chat_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"{CB_CHANNEL_PREFIX}{chat_id}")],
        ]
    )


def inline_logs() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Сбросить ошибку", callback_data=CB_LOGS_CLEAR)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def inline_admins(extra_ids: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[_section("АДМИНЫ")]]
    for uid in sorted(extra_ids):
        rows.append([
            InlineKeyboardButton(
                text=f"❌ Убрать {uid}",
                callback_data=f"{CB_ADMIN_REMOVE_PREFIX}{uid}",
            )
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data=CB_ADMIN_ADD)])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inline_after_update() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♻️ Перезапустить бота", callback_data=CB_UPDATE_RESTART)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CB_MENU)],
        ]
    )


def _ok(ok: bool) -> str:
    return "✅" if ok else "❌"


def dashboard(
    stats: dict,
    next_lines: list[str],
    window: str,
    text_preview: str | None,
    has_photo: bool,
) -> str:
    sched = "\n".join(f"  • {line}" for line in next_lines) if next_lines else "  • нет"
    preview = ""
    if text_preview:
        short = text_preview[:60] + ("…" if len(text_preview) > 60 else "")
        preview = f"\n<i>{short}</i>"

    return (
        f"🏠 <b>Автопостер v{BOT_VERSION}</b>\n"
        f"<i>Раздел: ГЛАВНАЯ</i>\n"
        f"Бот для ежедневных постов в каналы\n\n"
        f"📡 Каналов: <b>{stats['total']}</b>  "
        f"✅ Сегодня: <b>{stats['posted_today']}</b>  "
        f"⏳ Ждут: <b>{stats['pending_today']}</b>"
        + (
            f"  ⚠️ Частично: <b>{stats['partial_today']}</b>"
            if stats.get("partial_today")
            else ""
        )
        + "\n\n"
        f"{_ok(stats['has_text'])} Текст поста    "
        f"{_ok(has_photo)} Картинка"
        f"{preview}\n\n"
        f"🕐 Окно: <b>{window}</b>  ·  📤 <b>фото → текст</b>\n\n"
        f"<b>Ближайшие посты:</b>\n{sched}"
    )


def stats_page(stats: dict, next_lines: list[str], inactive: int, window: str) -> str:
    sched = "\n".join(f"  • {line}" for line in next_lines) if next_lines else "  • нет"
    return page(
        "📊",
        "Статистика",
        "РАССЫЛКА",
        f"📡 Активных каналов: <b>{stats['total']}</b>\n"
        f"✅ Опубликовано сегодня: <b>{stats['posted_today']}</b>\n"
        f"⏳ Ждут пост сегодня: <b>{stats['pending_today']}</b>\n"
        + (
            f"⚠️ Фото без текста: <b>{stats['partial_today']}</b>\n"
            if stats.get("partial_today")
            else ""
        )
        + f"💤 Неактивных в базе: <b>{inactive}</b>\n\n"
        f"{_ok(stats['has_text'])} Текст поста\n"
        f"{_ok(stats['has_photo'])} Картинка\n\n"
        f"🕐 Окно публикаций: <b>{window}</b>\n"
        f"📤 Порядок: <b>фото → текст</b>\n\n"
        f"<b>Ближайшие посты:</b>\n{sched}",
    )


def content_preview(text: str | None, has_photo: bool) -> str:
    if not text and not has_photo:
        body = "Контент ещё не задан.\nЗадайте текст и фото в разделе «КОНТЕНТ»."
    else:
        parts = []
        if text:
            preview = text[:400] + ("…" if len(text) > 400 else "")
            parts.append(f"<b>Текст:</b>\n{preview}")
        else:
            parts.append("❌ Текст не задан")
        parts.append("✅ Картинка загружена" if has_photo else "❌ Картинка не задана")
        body = "\n\n".join(parts)
    return page("👁", "Просмотр контента", "КОНТЕНТ", body)


def add_channel_help() -> str:
    return page(
        "➕",
        "Подключение канала",
        "КАНАЛЫ",
        "<b>Автоматически</b>\n"
        "Добавьте бота админом с правом «Управление публикациями» — "
        "канал подхватится сам.\n\n"
        "<b>Вручную</b> (если бот уже был админом до запуска)\n"
        "Нажмите «Добавить вручную» и отправьте:\n"
        "• @username канала\n"
        "• ссылку t.me/channel\n"
        "• пересланный пост из канала",
    )


def add_channel_manual_prompt() -> str:
    return page(
        "🔍",
        "Добавить канал вручную",
        "КАНАЛЫ",
        "Отправьте @username, ссылку t.me/…\n"
        "или перешлите любой пост из канала.",
    )


def channels_list(channels: list[tuple[int, str, str | None, str]], page: int, total: int) -> str:
    if not total:
        body = "Список пуст.\nДобавьте бота админом или используйте ручное добавление."
    else:
        start = page * CHANNELS_PER_PAGE
        lines = []
        for _, title, username, sched in channels[start : start + CHANNELS_PER_PAGE]:
            name = f"@{username}" if username else title
            lines.append(f"  • {name} — {sched}")
        body = (
            f"Всего: <b>{total}</b>  ·  стр. <b>{page + 1}</b>\n\n"
            + "\n".join(lines)
            + "\n\nВыберите канал для управления."
        )
    return page("📋", "Список каналов", "КАНАЛЫ", body)


def channel_detail(
    name: str,
    sched_time: str,
    sched_date: str,
    posted_today: bool,
    active: bool,
    partial: bool = False,
) -> str:
    if posted_today:
        today = "✅ опубликован"
    elif partial:
        today = "⚠️ фото без текста — повтор текста"
    else:
        today = "⏳ ждёт"
    status = "активен" if active else "неактивен"
    return page(
        "📡",
        name,
        "КАНАЛЫ",
        f"Статус: <b>{status}</b>\n"
        f"Сегодня: <b>{today}</b>\n"
        f"Время поста: <b>{sched_time}</b>\n"
        f"Дата слота: <b>{sched_date}</b>",
    )


def logs_page(last_error: str | None, errors: list[tuple]) -> str:
    if last_error:
        err_block = f"<b>Последняя ошибка:</b>\n{last_error}"
    else:
        err_block = "<b>Последняя ошибка:</b>\nнет"

    if errors:
        lines = []
        for created_at, name, detail in errors:
            text = detail or name
            lines.append(f"  • {created_at[11:16]} {name}\n    {text}")
        history = "<b>Недавние:</b>\n" + "\n".join(lines)
    else:
        history = "Ошибок в истории пока нет."

    body = (
        f"{err_block}\n\n{history}\n\n"
        "<i>После сбоя Telegram каналы с ошибкой постятся повторно — "
        "пока не уйдёт пост или не нажмёте «Отправить». "
        "Если фото уже ушло, повторится только текст.</i>"
    )
    return page("📜", "Логи", "СИСТЕМА", body)


def sys_page(
    version: str,
    window: str,
    delay: float,
    uptime: str,
    stats: dict,
    load: dict[str, str],
    last_backup: str | None,
    last_ok: str | None,
) -> str:
    backup_s = last_backup or "ещё не было"
    ok_s = last_ok or "—"
    partial = stats.get("partial_today", 0)
    return page(
        "💻",
        "Нагрузка системы",
        "СИСТЕМА",
        f"CPU: <b>{load['cpu']}</b>\n"
        f"RAM: <b>{load['ram']}</b>\n"
        f"Диск: <b>{load['disk']}</b>\n\n"
        f"Бот v<b>{version}</b>  ·  Uptime: <b>{uptime}</b>\n"
        f"Окно постов: <b>{window}</b>  ·  Пауза: <b>{delay} сек</b>\n\n"
        f"Каналов: <b>{stats['total']}</b>  ·  "
        f"Ждут пост: <b>{stats['pending_today']}</b>\n"
        f"Частичных сегодня: <b>{partial}</b>\n"
        f"Последний успешный пост: <b>{ok_s}</b>\n"
        f"Бэкап БД: <b>{backup_s}</b>",
    )


def reload_prompt() -> str:
    return page(
        "🔄",
        "Перезагрузка",
        "СИСТЕМА",
        "Обновит конфиг, админов и расписание,\n"
        "затем перезапустит процесс бота.",
    )


def reload_done() -> str:
    return page("♻️", "Перезапуск", "СИСТЕМА", "Бот перезапускается…")


def update_result(ok: bool, output: str) -> str:
    status = "✅ Обновление выполнено" if ok else "❌ Ошибка обновления"
    hint = "Нажмите «Перезапустить бота», если код изменился." if ok else ""
    return page("⬆️", "Обновление", "СИСТЕМА", f"{status}\n\n<code>{output}</code>\n\n{hint}")


def admins_page(admin_ids: list[int], owner_ids: set[int], extra_ids: list[int]) -> str:
    lines = []
    for aid in sorted(admin_ids):
        if aid in owner_ids:
            tag = " · владелец"
        elif aid in extra_ids:
            tag = " · можно убрать"
        else:
            tag = ""
        lines.append(f"  • <code>{aid}</code>{tag}")
    body = "\n".join(lines) if lines else "  • нет"
    return page(
        "🔑",
        "Администраторы",
        "СИСТЕМА",
        f"Доступ к боту:\n{body}\n\n"
        "Владельцы из .env добавляют и убирают остальных.",
    )


def help_text(window: str) -> str:
    return page(
        "❓",
        "Справка",
        "ПРОЧЕЕ",
        "<b>Каналы</b>\n"
        "➕ Подключить — авто и ручное добавление\n"
        "📋 Список — отправка, расписание, удаление\n\n"
        "<b>Контент</b>\n"
        "📝 Текст · 🖼 Фото · 👁 Просмотр\n\n"
        "<b>Рассылка</b>\n"
        f"Случайное время {window}, фото → текст\n"
        "🚀 Отправить все · 🔄 Перегенерировать\n\n"
        "<b>Система</b>\n"
        "💻 Нагрузка · 📜 Логи · 🔑 Админы\n"
        "🔄 Перезагрузка · ⬆️ Обновление (git pull)",
    )


def clear_menu() -> str:
    return page(
        "🗑",
        "Очистка базы",
        "КАНАЛЫ",
        "Выберите, что удалить из базы каналов.\n"
        "Текст и фото поста сохранятся.",
    )


def send_confirm(count: int) -> str:
    return page(
        "🚀",
        "Отправка сейчас",
        "РАССЫЛКА",
        f"Отправить пост в <b>{count}</b> каналов?\n"
        "Порядок: фото → пауза → текст",
    )


def send_one_confirm(name: str) -> str:
    return page(
        "🚀",
        "Отправка в канал",
        "КАНАЛЫ",
        f"Отправить пост в <b>{name}</b>?\n"
        "Даже если сегодня уже был пост.",
    )


def regen_confirm(count: int) -> str:
    return page(
        "🔄",
        "Перегенерация расписания",
        "РАССЫЛКА",
        f"Назначить новое случайное время для <b>{count}</b> каналов?\n"
        "Сбросит отметку «опубликовано» на сегодня.",
    )


def remove_confirm(name: str) -> str:
    return page(
        "❌",
        "Удаление канала",
        "КАНАЛЫ",
        f"Удалить <b>{name}</b> из базы?\n"
        "Из Telegram канал не удалится.",
    )


def settext_prompt() -> str:
    return page(
        "📝",
        "Текст поста",
        "КОНТЕНТ",
        "Отправьте текст одним сообщением.\n"
        "Он будет использоваться во всех каналах.",
    )


def setphoto_prompt() -> str:
    return page(
        "🖼",
        "Картинка поста",
        "КОНТЕНТ",
        "Отправьте картинку следующим сообщением.\n"
        "Она будет использоваться во всех каналах.",
    )


def admin_add_prompt() -> str:
    return page(
        "➕",
        "Новый администратор",
        "СИСТЕМА",
        "Отправьте Telegram ID числом\n"
        "или перешлите сообщение от пользователя.",
    )

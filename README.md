# Telegram channel autoposter (Bot API)

Бот-админ в каналах. Сам подхватывает каналы при выдаче прав.

## Логика

- Каждый день **новое случайное время** (08:00–22:00) на канал
- В это время: **картинка → пауза 1.5 сек → текст** (два сообщения)
- Один текст и одно фото на все каналы (задаёте в боте)

## Запуск

```bash
pip install -r requirements.txt
copy .env.example .env
# BOT_TOKEN от @BotFather, ADMIN_IDS — ваш Telegram id
python main.py
```

## Управление

Только команда `/start` — дальше всё через **кнопки меню**:

| Раздел | Возможности |
|--------|-------------|
| Контент | текст, фото, просмотр |
| Рассылка | статистика, отправить всем, перегенерировать расписание |
| Каналы | список, ручное добавление, отправка в один канал, удаление, очистка |
| Система | нагрузка CPU/RAM, логи, админы, перезагрузка, git pull |
| Справка | подсказки |

## Подключение канала

1. Создайте канал
2. Добавьте бота **админом** с правом **«Управление публикациями»**
3. Канал подхватится автоматически
4. Если бот уже был админом — **➕ Подключить → Добавить вручную**

## VPS

Бот должен работать 24/7. Рекомендуется **systemd** (см. `deploy/tg-bot.service`):

```bash
sudo useradd -r -m -d /opt/tg_bot tgbot
sudo cp -r . /opt/tg_bot
sudo -u tgbot python -m venv /opt/tg_bot/.venv
sudo -u tgbot /opt/tg_bot/.venv/bin/pip install -r /opt/tg_bot/requirements.txt
# .env в /opt/tg_bot/.env

sudo cp deploy/tg-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tg-bot
```

Локально или без systemd: `python main.py` — при падении перезапуск через 3 сек; второй процесс с той же базой блокируется (`data/bot.lock`).

Ежедневно в **00:05** — новое расписание и бэкап БД в `data/backups/` (14 дней).

Кнопка «Перезагрузка» в боте перезапускает процесс.

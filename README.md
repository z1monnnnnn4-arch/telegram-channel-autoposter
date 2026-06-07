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

## VPS (рядом с другими ботами)

Автопостер **не мешает** funpay-universal и другим ботам, если:

- **другой токен** BotFather (у вас `@z1monPost_bot` — отдельный бот);
- **отдельная папка** и свой venv (не смешивать с `/root/funpayuniversal`);
- **отдельный systemd-сервис** (funpay — `fpuniversal`, автопостер — `tg-bot`).

Оба бота ходят в Telegram API через long polling — порты открывать не нужно.

### Установка на Ubuntu (пример: `/opt/tg_bot`)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip

sudo git clone https://github.com/z1monnnnnn4-arch/telegram-channel-autoposter.git /opt/tg_bot
sudo chown -R $USER:$USER /opt/tg_bot
cd /opt/tg_bot

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env   # BOT_TOKEN, ADMIN_IDS

# проверка
.venv/bin/python main.py
# Ctrl+C после «started v1.2»
```

### systemd

```bash
sudo cp deploy/tg-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tg-bot
sudo systemctl status tg-bot
```

Логи: `journalctl -u tg-bot -f`

Остановка: `sudo systemctl stop tg-bot`

### Если funpay уже в `/root/funpayuniversal`

Автопостер лучше положить **не туда**, а в `/opt/tg_bot` (или `/root/tg_bot`) — отдельно.

Управление funpay: `fpuniversal status` / `fpuniversal start` — это другой процесс, конфликта нет.

Ежедневно в **00:05** — новое расписание и бэкап БД в `data/backups/` (14 дней).

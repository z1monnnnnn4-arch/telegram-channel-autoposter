# Telegram channel autoposter (Bot API)

Бот `@z1monPost_bot` — админ в каналах, раз в день постит **фото → текст** в случайное время (08:00–22:00).

Репозиторий: https://github.com/z1monnnnnn4-arch/telegram-channel-autoposter

---

## Логика

- Каждый день **новое случайное время** на канал (окно задаётся в `.env`)
- Порядок: **картинка → пауза 1.5 сек → текст**
- Один текст и одно фото на **все** каналы (задаёте в боте)
- Бот сам подхватывает каналы, когда его добавляют админом
- Сняли с админов → канал **деактивируется** в базе (не удаляется). Удалить: **КАНАЛЫ → Очистка → Неактивные**

---

## Файлы на сервере

| Путь | Что там |
|------|---------|
| `/root/tg_bot/` | код бота |
| `/root/tg_bot/.env` | секреты (не в git!) |
| `/root/tg_bot/data/bot.db` | база каналов и расписания |
| `/root/tg_bot/data/backups/` | ежедневные бэкапы БД (14 дней) |
| `/root/tg_bot/data/bot.lock` | lock-файл (второй процесс не стартует) |
| `/etc/systemd/system/tg-bot.service` | автозапуск |

FunPay и другие боты — **в других папках** (например `/root/funpayuniversal`). Не смешивать.

---

## Настройка `.env`

```bash
cp .env.example .env
nano .env
```

```env
BOT_TOKEN=123456:ABC...          # от @BotFather
ADMIN_IDS=123456789              # ваш Telegram id (несколько через запятую)

POST_WINDOW_START=08:00          # окно случайного времени поста
POST_WINDOW_END=22:00
CHANNEL_DELAY_SEC=4              # пауза между каналами при массовой отправке
DB_PATH=data/bot.db
```

Узнать свой id: @userinfobot

---

## Установка на Ubuntu (VPS)

Подключиться по SSH и выполнить **по порядку**.

### 1. Скачать код

**Вариант A — git (удобно для обновлений):**

```bash
cd /root
git clone https://github.com/z1monnnnnn4-arch/telegram-channel-autoposter.git tg_bot
cd tg_bot
```

**Вариант B — zip с GitHub:**

Залить архив в `/root`, переименовать:

```bash
cd /root
mv telegram-channel-autoposter-main tg_bot
cd tg_bot
```

> С zip обновление через `git pull` не работает — только повторная заливка или переход на git clone.

### 2. Python и зависимости

```bash
apt update
apt install -y python3 python3-venv python3-pip git

cd /root/tg_bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Конфиг

```bash
cp .env.example .env
nano .env
```

### 4. Пробный запуск

```bash
.venv/bin/python main.py
```

Должно быть: `started v1.2` и `Run polling for bot @z1monPost_bot`.

Остановка: **Ctrl+C**.

### 5. Автозапуск (systemd)

```bash
cat > /etc/systemd/system/tg-bot.service << 'EOF'
[Unit]
Description=Telegram channel autoposter
After=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/tg_bot
EnvironmentFile=/root/tg_bot/.env
ExecStart=/root/tg_bot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now tg-bot
systemctl status tg-bot
```

Или из репозитория (если путь `/root/tg_bot`):

```bash
cp deploy/tg-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tg-bot
```

---

## Команды на сервере

### Автопостер (tg-bot)

```bash
systemctl status tg-bot       # статус
systemctl start tg-bot        # запуск
systemctl stop tg-bot         # остановка
systemctl restart tg-bot      # перезапуск
journalctl -u tg-bot -f       # логи в реальном времени
journalctl -u tg-bot -n 100   # последние 100 строк логов
```

### FunPay (если установлен рядом)

```bash
fpuniversal status
fpuniversal start
fpuniversal stop
fpuniversal restart
fpuniversal log
```

Оба бота **не мешают** друг другу: разные токены, папки и systemd-сервисы.

### Привязка zip-установки к GitHub (один раз)

```bash
systemctl stop tg-bot

cd /root/tg_bot
git init
git remote add origin https://github.com/z1monnnnnn4-arch/telegram-channel-autoposter.git
git fetch origin
git checkout -b main
git reset --hard origin/main
git branch --set-upstream-to=origin/main main

.venv/bin/pip install -r requirements.txt
systemctl start tg-bot
```

`.env` и `data/` не удалятся.

### Обновление кода

```bash
cd /root/tg_bot
git pull origin main
.venv/bin/pip install -r requirements.txt
systemctl restart tg-bot
```

Или кнопка **СИСТЕМА → ⬆️ Обновление → Перезапустить** в боте.

Если ошибка *no tracking information* — на сервере один раз:

```bash
cd /root/tg_bot
git branch --set-upstream-to=origin/main main
```

### Если пишет «Бот уже запущен (PID …)»

```bash
systemctl stop tg-bot
rm -f /root/tg_bot/data/bot.lock
systemctl start tg-bot
```

---

## Запуск на Windows (локально)

```powershell
cd D:\tg_bot
pip install -r requirements.txt
copy .env.example .env
# заполнить .env
python main.py
```

Остановка: **Ctrl+C**. Если не помогает:

```powershell
Get-Process python* | Stop-Process -Force
Remove-Item data\bot.lock -Force -ErrorAction SilentlyContinue
```

---

## Управление в Telegram

Только `/start` — дальше **кнопки меню**:

| Раздел | Возможности |
|--------|-------------|
| **КОНТЕНТ** | текст, фото, просмотр |
| **РАССЫЛКА** | статистика, отправить всем, перегенерировать расписание |
| **КАНАЛЫ** | список, ручное добавление, пост в один канал, удаление, очистка |
| **СИСТЕМА** | нагрузка, логи, админы, перезагрузка, git pull |
| **СПРАВКА** | подсказки |

### Подключение канала

1. Создайте канал (приватный или публичный)
2. Добавьте `@z1monPost_bot` **админом** с правом **«Управление публикациями»**
3. Канал подхватится сам
4. Если бот уже был админом до запуска — **КАНАЛЫ → Подключить → Добавить вручную**

---

## Автоматика

- Каждую минуту проверяет, кому пора постить
- **00:05** — новое расписание на день + бэкап БД
- При падении процесса systemd перезапускает через 5 сек
- Фото ушло, текст нет → повтор только текста (без второго фото)

---

## Быстрая шпаргалка после установки

```bash
# всё ли работает?
systemctl status tg-bot
fpuniversal status

# смотреть логи автопостера
journalctl -u tg-bot -f

# перезапуск автопостера
systemctl restart tg-bot
```

В Telegram: `/start` → **КОНТЕНТ** (текст + фото) → добавить бота в каналы.

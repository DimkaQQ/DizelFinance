# 🚀 ПОЛНАЯ ИНСТРУКЦИЯ ПО РАЗВЁРТЫВАНИЮ FINANCE BOT

## 📋 СОДЕРЖАНИЕ
1. [Требования](#требования)
2. [Настройка Telegram Bot](#настройка-telegram-bot)
3. [Настройка Google Sheets API](#настройка-google-sheets-api)
4. [Настройка Gmail API](#настройка-gmail-api)
5. [Установка и запуск](#установка-и-запуск)
6. [Настройка iPhone Shortcuts](#настройка-iphone-shortcuts)
7. [Развёртывание на сервере](#развёртывание-на-сервере)
8. [Troubleshooting](#troubleshooting)

---

## ТРЕБОВАНИЯ

### Минимальные требования:
- Python 3.8+
- Telegram аккаунт
- Google аккаунт
- iPhone (для SMS парсинга)
- VPS сервер (для продакшена) или локальный компьютер (для тестирования)

---

## НАСТРОЙКА TELEGRAM BOT

### ШАГ 1: Создайте бота

1. Откройте Telegram
2. Найдите **@BotFather**
3. Отправьте команду `/newbot`
4. Введите имя бота (например: "My Finance Bot")
5. Введите username (например: "my_finance_bot")
6. Скопируйте **токен** (например: `123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`)

### ШАГ 2: Узнайте свой Telegram ID

1. Найдите бота **@userinfobot**
2. Нажмите `/start`
3. Скопируйте ваш **ID** (например: `123456789`)

---

## НАСТРОЙКА GOOGLE SHEETS API

### ШАГ 1: Создайте проект в Google Cloud

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Нажмите "Создать проект"
3. Введите название: "Finance Bot"
4. Нажмите "Создать"

### ШАГ 2: Включите Google Sheets API

1. В меню слева выберите "API и сервисы" → "Библиотека"
2. Найдите "Google Sheets API"
3. Нажмите "Включить"

### ШАГ 3: Создайте Service Account

1. Перейдите в "API и сервисы" → "Учётные данные"
2. Нажмите "Создать учётные данные" → "Сервисный аккаунт"
3. Введите название: "finance-bot-service"
4. Нажмите "Создать и продолжить"
5. Роль: "Редактор"
6. Нажмите "Готово"

### ШАГ 4: Скачайте JSON ключ

1. В списке сервисных аккаунтов найдите созданный
2. Нажмите на него
3. Вкладка "Ключи" → "Добавить ключ" → "Создать новый ключ"
4. Выберите формат: **JSON**
5. Нажмите "Создать"
6. Файл автоматически скачается
7. **Переименуйте** файл в `finance-key.json`

### ШАГ 5: Дайте доступ к таблице

1. Откройте скачанный `finance-key.json`
2. Найдите строку `"client_email": "finance-bot-service@..."`
3. Скопируйте этот email
4. Откройте вашу [Google Таблицу](https://docs.google.com/spreadsheets/d/14tEIq0WtwTiplQ28JyBT04NYQ5BCKP7t2xUG1kpbFDU/edit)
5. Нажмите "Настройки доступа" (справа вверху)
6. Вставьте скопированный email
7. Выберите роль: "Редактор"
8. Нажмите "Готово"

---

## НАСТРОЙКА GMAIL API (для Email парсера)

### ШАГ 1: Включите Gmail API

1. В [Google Cloud Console](https://console.cloud.google.com/)
2. Перейдите в "API и сервисы" → "Библиотека"
3. Найдите "Gmail API"
4. Нажмите "Включить"

### ШАГ 2: Создайте OAuth 2.0 credentials

1. Перейдите в "API и сервисы" → "Учётные данные"
2. Нажмите "Создать учётные данные" → "Идентификатор клиента OAuth"
3. Тип приложения: "Приложение для ПК"
4. Имя: "Gmail Parser"
5. Нажмите "Создать"
6. Скачайте JSON файл
7. **Переименуйте** в `credentials.json`

### ШАГ 3: Настройте OAuth consent screen

1. Перейдите в "API и сервисы" → "OAuth consent screen"
2. User Type: "Внешний" (External)
3. Нажмите "Создать"
4. Заполните:
   - Название приложения: "Finance Bot"
   - Email поддержки: ваш email
5. Добавьте тестовых пользователей (ваш email)
6. Сохраните

---

## УСТАНОВКА И ЗАПУСК

### ШАГ 1: Клонируйте проект

```bash
# Создайте папку для проекта
mkdir finance-bot
cd finance-bot

# Скопируйте все файлы:
# - finance_bot.py
# - gmail_parser.py
# - requirements.txt
# - .env.example
# - finance-key.json (из Google Cloud)
# - credentials.json (из Google Cloud)
```

### ШАГ 2: Установите зависимости

```bash
# Создайте виртуальное окружение
python3 -m venv venv

# Активируйте его
# На macOS/Linux:
source venv/bin/activate
# На Windows:
venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt
```

### ШАГ 3: Настройте .env файл

```bash
# Скопируйте пример
cp .env.example .env

# Отредактируйте .env (используйте nano, vim или любой текстовый редактор)
nano .env
```

**Заполните:**
```
TELEGRAM_TOKEN=123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
ADMIN_TELEGRAM_ID=123456789
ALLOWED_USER_IDS=123456789
SHEET_URL=https://docs.google.com/spreadsheets/d/14tEIq0WtwTiplQ28JyBT04NYQ5BCKP7t2xUG1kpbFDU/edit
WEBHOOK_URL=http://localhost:5000/webhook/transaction
```

### ШАГ 4: Запустите бота (локально)

```bash
python finance_bot.py
```

**Вы должны увидеть:**
```
INFO:root:🚀 Finance Bot запущен!
```

### ШАГ 5: Протестируйте бота

1. Откройте Telegram
2. Найдите вашего бота (@your_bot_username)
3. Нажмите `/start`
4. Попробуйте добавить транзакцию: "➕ Новая транзакция"

---

## НАСТРОЙКА GMAIL ПАРСЕРА (Email автоматизация)

### ШАГ 1: Первый запуск (авторизация)

```bash
# В отдельном терминале
python gmail_parser.py
```

**Что произойдёт:**
1. Откроется браузер с запросом доступа к Gmail
2. Войдите в Google аккаунт
3. Разрешите доступ
4. Закройте браузер
5. В папке появится файл `token.json` (не удаляйте его!)

### ШАГ 2: Тестирование

1. Попросите кого-то отправить вам тестовое письмо от имени банка
2. Или **форвардните** реальное письмо от банка себе
3. Gmail парсер должен найти его и отправить в бота

**Пример тестового письма (Тинькофф):**
```
От: notify@tinkoff.ru
Тема: Покупка

Покупка 1500 ₽. Пятёрочка. Карта *4321. Баланс: 25000 ₽
```

---

## НАСТРОЙКА IPHONE SHORTCUTS (SMS автоматизация)

### Читайте полную инструкцию в файле:
👉 **[iPhone_Shortcuts_Setup.md](iPhone_Shortcuts_Setup.md)**

### Краткая версия:

1. Откройте приложение "Shortcuts" (Команды)
2. Создайте автоматизацию: "Когда приходит сообщение"
3. Отправитель: `Tinkoff` (или номер банка)
4. Добавьте действия:
   - Get Latest Messages
   - Match Text (парсинг суммы, места, карты)
   - Get Contents of URL (отправка в webhook)
5. Сохраните и протестируйте

---

## РАЗВЁРТЫВАНИЕ НА СЕРВЕРЕ (продакшен)

### ВАРИАНТ 1: DigitalOcean / AWS / Google Cloud

#### ШАГ 1: Создайте VPS сервер
- OS: Ubuntu 22.04
- RAM: 1GB (минимум)
- CPU: 1 core

#### ШАГ 2: Подключитесь по SSH

```bash
ssh root@your_server_ip
```

#### ШАГ 3: Установите зависимости

```bash
# Обновите систему
apt update && apt upgrade -y

# Установите Python 3.10+
apt install python3 python3-pip python3-venv -y

# Установите nginx (для webhook)
apt install nginx -y
```

#### ШАГ 4: Скопируйте файлы на сервер

```bash
# На локальном компьютере
scp finance_bot.py gmail_parser.py requirements.txt .env finance-key.json credentials.json root@your_server_ip:/root/finance-bot/
```

#### ШАГ 5: Настройте окружение

```bash
# На сервере
cd /root/finance-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### ШАГ 6: Настройте systemd service

Создайте файл `/etc/systemd/system/finance-bot.service`:

```ini
[Unit]
Description=Finance Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/finance-bot
Environment="PATH=/root/finance-bot/venv/bin"
ExecStart=/root/finance-bot/venv/bin/python finance_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Создайте файл `/etc/systemd/system/gmail-parser.service`:

```ini
[Unit]
Description=Gmail Parser for Finance Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/finance-bot
Environment="PATH=/root/finance-bot/venv/bin"
ExecStart=/root/finance-bot/venv/bin/python gmail_parser.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустите сервисы:

```bash
systemctl daemon-reload
systemctl enable finance-bot gmail-parser
systemctl start finance-bot gmail-parser

# Проверьте статус
systemctl status finance-bot
systemctl status gmail-parser
```

#### ШАГ 7: Настройте nginx для webhook

Создайте файл `/etc/nginx/sites-available/finance-bot`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /webhook/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Активируйте конфигурацию:

```bash
ln -s /etc/nginx/sites-available/finance-bot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

#### ШАГ 8: Настройте SSL (HTTPS)

```bash
# Установите certbot
apt install certbot python3-certbot-nginx -y

# Получите SSL сертификат
certbot --nginx -d your-domain.com

# Автообновление сертификата
certbot renew --dry-run
```

#### ШАГ 9: Обновите .env

```bash
nano /root/finance-bot/.env
```

Измените `WEBHOOK_URL`:
```
WEBHOOK_URL=https://your-domain.com/webhook/transaction
```

Перезапустите сервисы:
```bash
systemctl restart finance-bot gmail-parser
```

---

### ВАРИАНТ 2: Локальный компьютер + ngrok (для тестирования)

#### ШАГ 1: Установите ngrok

Скачайте с [ngrok.com](https://ngrok.com/download)

#### ШАГ 2: Запустите ngrok

```bash
ngrok http 5000
```

**Вы увидите:**
```
Forwarding https://abc123.ngrok.io -> http://localhost:5000
```

#### ШАГ 3: Обновите .env

```bash
WEBHOOK_URL=https://abc123.ngrok.io/webhook/transaction
```

#### ШАГ 4: Перезапустите бота

```bash
python finance_bot.py
```

⚠️ **Важно:** При каждом перезапуске ngrok URL будет меняться!

---

## TROUBLESHOOTING

### ПРОБЛЕМА 1: Бот не отвечает

**Решение:**
1. Проверьте токен в `.env`
2. Убедитесь, что бот запущен: `systemctl status finance-bot`
3. Проверьте логи: `journalctl -u finance-bot -f`

### ПРОБЛЕМА 2: Ошибка доступа к Google Sheets

**Ошибка:**
```
gspread.exceptions.APIError: {"error": {"code": 403, "message": "PERMISSION_DENIED"}}
```

**Решение:**
1. Откройте `finance-key.json`
2. Скопируйте `client_email`
3. Дайте доступ к таблице этому email (Редактор)

### ПРОБЛЕМА 3: Gmail парсер не находит письма

**Решение:**
1. Проверьте, что Gmail API включен
2. Убедитесь, что письма от банка не в спаме
3. Проверьте паттерны в `BANK_PATTERNS` (возможно, формат SMS изменился)

### ПРОБЛЕМА 4: iPhone Shortcuts не отправляет данные

**Решение:**
1. Проверьте, что iPhone разблокирован
2. Убедитесь, что в Shortcuts разрешена автоматизация
3. Проверьте URL webhook (должен быть HTTPS для продакшена)
4. Протестируйте вручную (нажмите Play в Shortcuts)

### ПРОБЛЕМА 5: Webhook не доходит до бота

**Решение:**
1. Проверьте, что Flask запущен на порту 5000
2. Проверьте nginx конфигурацию
3. Убедитесь, что SSL настроен (для iPhone требуется HTTPS)
4. Проверьте firewall: `ufw status`

---

## ЛОГИ И МОНИТОРИНГ

### Просмотр логов бота

```bash
# Последние 100 строк
journalctl -u finance-bot -n 100

# Следить в реальном времени
journalctl -u finance-bot -f
```

### Просмотр логов Gmail парсера

```bash
journalctl -u gmail-parser -f
```

### Просмотр логов nginx

```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

---

## БЕЗОПАСНОСТЬ

### 1. Не храните credentials в Git

Добавьте в `.gitignore`:
```
.env
finance-key.json
credentials.json
token.json
```

### 2. Ограничьте доступ к серверу

```bash
# Настройте firewall
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable
```

### 3. Используйте только HTTPS

Для iPhone Shortcuts и Gmail парсера **требуется HTTPS**.

### 4. Ограничьте ALLOWED_USER_IDS

В `.env` укажите только доверенных пользователей:
```
ALLOWED_USER_IDS=123456789,987654321
```

---

## ОБНОВЛЕНИЕ БОТА

### На сервере:

```bash
cd /root/finance-bot

# Остановите сервисы
systemctl stop finance-bot gmail-parser

# Обновите файлы (через scp или git pull)
scp finance_bot.py root@your_server_ip:/root/finance-bot/

# Запустите заново
systemctl start finance-bot gmail-parser
```

---

## РЕЗЕРВНОЕ КОПИРОВАНИЕ

### Бэкап Google Sheets

Google Sheets автоматически сохраняет историю изменений.

Дополнительно:
1. Файл → Скачать → Excel (.xlsx)
2. Храните локальную копию

### Бэкап кода

```bash
# На сервере
cd /root/finance-bot
tar -czf backup_$(date +%Y%m%d).tar.gz *.py *.json .env
```

---

## ПОДДЕРЖКА

Если возникли проблемы:
1. Проверьте логи
2. Перечитайте инструкцию
3. Проверьте все credentials
4. Напишите в Issues на GitHub

**Удачи!** 🚀

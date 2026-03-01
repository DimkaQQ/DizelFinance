# 🔑 КАК ПОЛУЧИТЬ ВСЕ КЛЮЧИ И ТОКЕНЫ

## 📋 СОДЕРЖАНИЕ

1. [Telegram Bot Token](#1-telegram-bot-token)
2. [Telegram ID](#2-telegram-id)
3. [Google Sheets API (finance-key.json)](#3-google-sheets-api-finance-keyjson)
4. [Gmail API (credentials.json)](#4-gmail-api-credentialsjson)
5. [Проверка всех ключей](#5-проверка-всех-ключей)

---

## 1️⃣ TELEGRAM BOT TOKEN

### ШАГ 1: Создайте бота

1. Откройте Telegram на телефоне или в веб-версии
2. Найдите **@BotFather** (официальный бот Telegram)
3. Нажмите `/start`

### ШАГ 2: Создайте нового бота

Отправьте команду:
```
/newbot
```

### ШАГ 3: Введите имя бота

BotFather спросит:
```
Alright, a new bot. How are we going to call it? Please choose a name for your bot.
```

Ответьте (например):
```
My Finance Bot
```

### ШАГ 4: Введите username бота

BotFather спросит:
```
Good. Now let's choose a username for your bot. It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
```

Ответьте (например):
```
my_finance_bot
```

⚠️ **Важно:** username должен:
- Быть уникальным
- Заканчиваться на `bot`
- Содержать только буквы, цифры и подчёркивания

### ШАГ 5: Скопируйте токен

BotFather ответит:
```
Done! Congratulations on your new bot. You will find it at t.me/my_finance_bot. 

Use this token to access the HTTP API:
123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw

For a description of the Bot API, see this page: https://core.telegram.org/bots/api
```

**Скопируйте токен:**
```
123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

### ШАГ 6: Вставьте в .env

Откройте файл `.env` и вставьте:
```
TELEGRAM_TOKEN=123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

---

## 2️⃣ TELEGRAM ID

### ШАГ 1: Найдите бота

В Telegram найдите **@userinfobot**

### ШАГ 2: Запустите бота

Нажмите `/start`

### ШАГ 3: Скопируйте ID

Бот ответит:
```
Id: 123456789
First name: Ваше Имя
Username: @your_username
Language: ru
Is premium: true
```

**Скопируйте число после "Id:":**
```
123456789
```

### ШАГ 4: Вставьте в .env

Откройте файл `.env` и вставьте:
```
ADMIN_TELEGRAM_ID=123456789
ALLOWED_USER_IDS=123456789
```

⚠️ **Для семейного использования:**
Если несколько человек будут использовать бота, добавьте их ID через запятую:
```
ALLOWED_USER_IDS=123456789,987654321,555666777
```

---

## 3️⃣ GOOGLE SHEETS API (finance-key.json)

### ШАГ 1: Откройте Google Cloud Console

Перейдите на https://console.cloud.google.com/

### ШАГ 2: Создайте новый проект

1. Нажмите на название проекта вверху (или "Select a project")
2. Нажмите **"NEW PROJECT"**
3. Введите название: **Finance Bot**
4. Нажмите **"CREATE"**
5. Подождите 10-20 секунд

### ШАГ 3: Включите Google Sheets API

1. В меню слева выберите **"APIs & Services"** → **"Library"**
2. В поиске введите: **Google Sheets API**
3. Кликните на **Google Sheets API**
4. Нажмите **"ENABLE"**
5. Подождите 5-10 секунд

### ШАГ 4: Создайте Service Account

1. В меню слева выберите **"APIs & Services"** → **"Credentials"**
2. Нажмите **"+ CREATE CREDENTIALS"**
3. Выберите **"Service account"**
4. Заполните форму:
   - **Service account name:** `finance-bot-service`
   - **Service account ID:** (заполнится автоматически)
   - **Description:** `Service account for Finance Bot`
5. Нажмите **"CREATE AND CONTINUE"**
6. Выберите роль:
   - Кликните на поле **"Select a role"**
   - В поиске введите: `Editor`
   - Выберите **"Basic"** → **"Editor"**
7. Нажмите **"CONTINUE"**
8. Нажмите **"DONE"** (третий шаг можно пропустить)

### ШАГ 5: Создайте и скачайте JSON ключ

1. В списке Service accounts найдите `finance-bot-service@...`
2. Кликните на него
3. Перейдите на вкладку **"KEYS"**
4. Нажмите **"ADD KEY"** → **"Create new key"**
5. Выберите формат: **JSON**
6. Нажмите **"CREATE"**
7. Файл автоматически скачается (например: `finance-bot-123456-abc123def456.json`)

### ШАГ 6: Переименуйте файл

Переименуйте скачанный файл в:
```
finance-key.json
```

### ШАГ 7: Положите файл в папку с ботом

Скопируйте `finance-key.json` в папку, где находится `finance_bot.py`

```
finance-bot/
├── finance_bot.py
├── finance-key.json  ← СЮДА
├── .env
└── ...
```

### ШАГ 8: Дайте доступ к Google Таблице

1. Откройте файл `finance-key.json` в текстовом редакторе
2. Найдите строку:
   ```json
   "client_email": "finance-bot-service@finance-bot-123456.iam.gserviceaccount.com"
   ```
3. **Скопируйте весь email** (например: `finance-bot-service@finance-bot-123456.iam.gserviceaccount.com`)
4. Откройте вашу Google Таблицу:
   https://docs.google.com/spreadsheets/d/14tEIq0WtwTiplQ28JyBT04NYQ5BCKP7t2xUG1kpbFDU/edit
5. Нажмите кнопку **"Share"** (Настройки доступа) в правом верхнем углу
6. В поле **"Add people and groups"** вставьте скопированный email
7. Выберите роль: **"Editor"** (Редактор)
8. **Снимите галочку** "Notify people" (Уведомлять людей)
9. Нажмите **"Share"** (Предоставить доступ)

✅ **Готово!** Теперь бот может записывать данные в таблицу.

---

## 4️⃣ GMAIL API (credentials.json)

### ШАГ 1: Включите Gmail API

1. Вернитесь в Google Cloud Console: https://console.cloud.google.com/
2. Убедитесь, что выбран проект **"Finance Bot"**
3. В меню слева выберите **"APIs & Services"** → **"Library"**
4. В поиске введите: **Gmail API**
5. Кликните на **Gmail API**
6. Нажмите **"ENABLE"**
7. Подождите 5-10 секунд

### ШАГ 2: Настройте OAuth consent screen

1. В меню слева выберите **"APIs & Services"** → **"OAuth consent screen"**
2. Выберите **User Type:** **External** (Внешний)
3. Нажмите **"CREATE"**
4. Заполните форму:
   - **App name:** `Finance Bot`
   - **User support email:** ваш Gmail (например: `you@gmail.com`)
   - **Developer contact information:** ваш Gmail
5. Нажмите **"SAVE AND CONTINUE"**
6. На странице **"Scopes"** нажмите **"SAVE AND CONTINUE"** (ничего не добавляйте)
7. На странице **"Test users"** нажмите **"+ ADD USERS"**
8. Введите ваш Gmail (например: `you@gmail.com`)
9. Нажмите **"ADD"**
10. Нажмите **"SAVE AND CONTINUE"**
11. Нажмите **"BACK TO DASHBOARD"**

### ШАГ 3: Создайте OAuth 2.0 Client ID

1. В меню слева выберите **"APIs & Services"** → **"Credentials"**
2. Нажмите **"+ CREATE CREDENTIALS"**
3. Выберите **"OAuth client ID"**
4. **Application type:** выберите **"Desktop app"** (Приложение для ПК)
5. **Name:** введите `Gmail Parser`
6. Нажмите **"CREATE"**
7. В появившемся окне нажмите **"DOWNLOAD JSON"**

### ШАГ 4: Переименуйте файл

Переименуйте скачанный файл (например: `client_secret_123456789-abc.apps.googleusercontent.com.json`) в:
```
credentials.json
```

### ШАГ 5: Положите файл в папку с ботом

Скопируйте `credentials.json` в папку, где находится `gmail_parser.py`

```
finance-bot/
├── gmail_parser.py
├── credentials.json  ← СЮДА
├── finance-key.json
├── .env
└── ...
```

### ШАГ 6: Первый запуск (авторизация)

При первом запуске `gmail_parser.py` откроется браузер:

```bash
python gmail_parser.py
```

**Что произойдёт:**
1. Откроется браузер с Google OAuth
2. Выберите ваш аккаунт Gmail
3. Появится предупреждение **"Google hasn't verified this app"**
4. Нажмите **"Advanced"** (Дополнительно)
5. Нажмите **"Go to Finance Bot (unsafe)"** (Перейти к приложению)
6. Нажмите **"Allow"** (Разрешить)
7. Закройте браузер

В папке появится файл `token.json` — **не удаляйте его!**

✅ **Готово!** Gmail парсер авторизован.

---

## 5️⃣ ПРОВЕРКА ВСЕХ КЛЮЧЕЙ

### Проверка 1: Telegram токен

```bash
python -c "
from aiogram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TELEGRAM_TOKEN')

if not token:
    print('❌ TELEGRAM_TOKEN не найден в .env')
    exit(1)

try:
    bot = Bot(token=token)
    import asyncio
    asyncio.run(bot.get_me())
    print('✅ Telegram токен валиден!')
except Exception as e:
    print(f'❌ Ошибка: {e}')
"
```

### Проверка 2: Google Sheets доступ

```bash
python -c "
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv

load_dotenv()
sheet_url = os.getenv('SHEET_URL')

try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('finance-key.json', scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    print(f'✅ Доступ к таблице есть! Название: {sh.title}')
except FileNotFoundError:
    print('❌ Файл finance-key.json не найден')
except Exception as e:
    print(f'❌ Ошибка: {e}')
"
```

### Проверка 3: Gmail API

```bash
python -c "
import os
if os.path.exists('credentials.json'):
    print('✅ credentials.json найден')
else:
    print('❌ credentials.json не найден')

if os.path.exists('token.json'):
    print('✅ token.json найден (Gmail авторизован)')
else:
    print('⚠️ token.json не найден (запустите gmail_parser.py для авторизации)')
"
```

### Проверка 4: Все переменные окружения

```bash
python -c "
import os
from dotenv import load_dotenv

load_dotenv()

required = [
    'TELEGRAM_TOKEN',
    'ADMIN_TELEGRAM_ID',
    'ALLOWED_USER_IDS',
    'SHEET_URL',
    'WEBHOOK_URL'
]

for var in required:
    value = os.getenv(var)
    if value:
        print(f'✅ {var}: {value[:20]}...')
    else:
        print(f'❌ {var}: НЕ ЗАДАН!')
"
```

---

## 🎉 ВСЁ ГОТОВО!

Если все проверки прошли успешно:

```
✅ Telegram токен валиден!
✅ Доступ к таблице есть! Название: Василий_Финансы
✅ credentials.json найден
✅ token.json найден (Gmail авторизован)
✅ TELEGRAM_TOKEN: 123456789:AAHdqTcv...
✅ ADMIN_TELEGRAM_ID: 123456789
✅ ALLOWED_USER_IDS: 123456789
✅ SHEET_URL: https://docs.google....
✅ WEBHOOK_URL: http://localhost:5000...
```

**Теперь можно запускать бота:**

```bash
python finance_bot.py
```

---

## 🐛 TROUBLESHOOTING

### Ошибка: "TELEGRAM_TOKEN не найден"
- Проверьте, что файл `.env` находится в той же папке, что и `finance_bot.py`
- Убедитесь, что в `.env` нет лишних пробелов: `TELEGRAM_TOKEN=123...` (без пробелов вокруг `=`)

### Ошибка: "finance-key.json не найден"
- Проверьте название файла (должно быть **точно** `finance-key.json`)
- Убедитесь, что файл находится в той же папке, что и `finance_bot.py`

### Ошибка: "APIError: PERMISSION_DENIED"
- Откройте `finance-key.json`
- Скопируйте `client_email`
- Дайте доступ этому email к таблице (Редактор)

### Ошибка при запуске gmail_parser.py
- Убедитесь, что `credentials.json` находится в папке
- При первом запуске должен открыться браузер для авторизации
- Если браузер не открывается — проверьте firewall

---

**Удачи!** 🚀

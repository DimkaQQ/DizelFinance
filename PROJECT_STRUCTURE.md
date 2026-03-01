# 📁 СТРУКТУРА ПРОЕКТА FINANCE BOT

## 🗂️ ПОЛНАЯ СТРУКТУРА ФАЙЛОВ

```
finance-bot/
│
├── 📄 finance_bot.py                    # Основной Telegram бот (22 KB)
├── 📄 gmail_parser.py                   # Email парсер (8 KB)
├── 📄 requirements.txt                  # Python зависимости
│
├── 🔐 .env                              # Конфигурация (СОЗДАТЬ ВРУЧНУЮ)
├── 🔐 finance-key.json                  # Google Sheets API ключ (СКАЧАТЬ)
├── 🔐 credentials.json                  # Gmail API ключ (СКАЧАТЬ)
├── 🔐 token.json                        # Gmail OAuth токен (создаётся автоматически)
│
├── 📖 README.md                         # Краткое описание проекта
├── 📖 DEPLOYMENT.md                     # Полная инструкция по развёртыванию
├── 📖 HOW_TO_GET_KEYS.md               # Как получить все ключи и токены
├── 📖 TABLE_ANALYSIS.md                # Анализ и исправление ошибок в таблице
├── 📖 iPhone_Shortcuts_Setup.md        # Настройка iOS автоматизации
│
├── 📝 .env.example                      # Пример конфигурации
├── 📝 finance-key.json.example         # Пример Google Sheets ключа
├── 📝 credentials.json.example         # Пример Gmail ключа
├── 📝 .gitignore                        # Игнорируемые файлы для Git
│
└── 📂 (опционально для продакшена)
    ├── systemd/
    │   ├── finance-bot.service          # Systemd сервис для бота
    │   └── gmail-parser.service         # Systemd сервис для парсера
    └── nginx/
        └── finance-bot.conf             # Nginx конфигурация для webhook
```

---

## 📋 ОПИСАНИЕ ФАЙЛОВ

### 🤖 ОСНОВНЫЕ ФАЙЛЫ (код бота)

| Файл                  | Размер | Описание |
|-----------------------|--------|----------|
| `finance_bot.py`      | 22 KB  | Основной Telegram бот с FSM для диалогов, webhook для SMS/Email |
| `gmail_parser.py`     | 8 KB   | Автоматический парсер Email от банков (Тинькофф, Альфа, Сбер) |
| `requirements.txt`    | 213 B  | Python зависимости (aiogram, gspread, flask и др.) |

---

### 🔐 КОНФИДЕНЦИАЛЬНЫЕ ФАЙЛЫ (создать вручную)

| Файл                | Откуда взять | Инструкция |
|---------------------|--------------|------------|
| `.env`              | Создать вручную | [HOW_TO_GET_KEYS.md](#) |
| `finance-key.json`  | Google Cloud Console | [HOW_TO_GET_KEYS.md](#) → Раздел 3 |
| `credentials.json`  | Google Cloud Console | [HOW_TO_GET_KEYS.md](#) → Раздел 4 |
| `token.json`        | Создаётся автоматически | Появится после первого запуска `gmail_parser.py` |

⚠️ **ВАЖНО:** Эти файлы содержат секретные ключи! Никогда не публикуйте их в Git или где-либо ещё.

---

### 📖 ДОКУМЕНТАЦИЯ (инструкции)

| Файл                         | Описание |
|------------------------------|----------|
| `README.md`                  | Краткое описание проекта, быстрый старт |
| `DEPLOYMENT.md`              | Полная инструкция по развёртыванию (локально и на VPS) |
| `HOW_TO_GET_KEYS.md`        | Пошаговая инструкция как получить все ключи и токены |
| `TABLE_ANALYSIS.md`         | Анализ Google Sheets: найденные ошибки и как их исправить |
| `iPhone_Shortcuts_Setup.md` | Настройка iOS автоматизации для SMS от банков |

---

### 📝 ПРИМЕРЫ (для справки)

| Файл                          | Описание |
|-------------------------------|----------|
| `.env.example`                | Пример файла `.env` с объяснениями каждой переменной |
| `finance-key.json.example`    | Пример структуры Google Service Account ключа |
| `credentials.json.example`    | Пример структуры Gmail OAuth ключа |
| `.gitignore`                  | Список файлов которые НЕ нужно добавлять в Git |

---

## 🚀 КАКИЕ ФАЙЛЫ НУЖНО СОЗДАТЬ?

### ✅ УЖЕ ГОТОВЫ (скачайте)

- ✅ `finance_bot.py`
- ✅ `gmail_parser.py`
- ✅ `requirements.txt`
- ✅ `README.md`
- ✅ `DEPLOYMENT.md`
- ✅ `HOW_TO_GET_KEYS.md`
- ✅ `TABLE_ANALYSIS.md`
- ✅ `iPhone_Shortcuts_Setup.md`
- ✅ `.env.example`
- ✅ `finance-key.json.example`
- ✅ `credentials.json.example`
- ✅ `.gitignore`

### ❌ НУЖНО СОЗДАТЬ ВРУЧНУЮ

#### 1. `.env` — конфигурация

```bash
# Скопируйте пример
cp .env.example .env

# Откройте в редакторе
nano .env

# Заполните все переменные:
TELEGRAM_TOKEN=ваш_токен_от_BotFather
ADMIN_TELEGRAM_ID=ваш_telegram_id
ALLOWED_USER_IDS=ваш_telegram_id
SHEET_URL=https://docs.google.com/spreadsheets/d/14tEIq0WtwTiplQ28JyBT04NYQ5BCKP7t2xUG1kpbFDU/edit
WEBHOOK_URL=http://localhost:5000/webhook/transaction
```

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Разделы 1 и 2

---

#### 2. `finance-key.json` — Google Sheets API ключ

```bash
# Этот файл нужно СКАЧАТЬ из Google Cloud Console
# Инструкция: HOW_TO_GET_KEYS.md → Раздел 3

# Шаги:
1. Создайте проект в Google Cloud Console
2. Включите Google Sheets API
3. Создайте Service Account
4. Скачайте JSON ключ
5. Переименуйте в finance-key.json
6. Положите в папку с ботом
```

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Раздел 3 (подробно)

---

#### 3. `credentials.json` — Gmail API ключ

```bash
# Этот файл нужно СКАЧАТЬ из Google Cloud Console
# Инструкция: HOW_TO_GET_KEYS.md → Раздел 4

# Шаги:
1. Включите Gmail API
2. Настройте OAuth consent screen
3. Создайте OAuth 2.0 Client ID (Desktop app)
4. Скачайте JSON
5. Переименуйте в credentials.json
6. Положите в папку с ботом
```

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Раздел 4 (подробно)

---

#### 4. `token.json` — Gmail OAuth токен

```bash
# Этот файл создаётся АВТОМАТИЧЕСКИ при первом запуске gmail_parser.py

# Шаги:
1. Убедитесь, что credentials.json находится в папке
2. Запустите: python gmail_parser.py
3. Откроется браузер → войдите в Google → разрешите доступ
4. Файл token.json создастся автоматически
5. НЕ УДАЛЯЙТЕ его!
```

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Раздел 4, Шаг 6

---

## 📦 МИНИМАЛЬНАЯ СТРУКТУРА ДЛЯ ЗАПУСКА

Чтобы бот запустился, нужны **минимум 4 файла**:

```
finance-bot/
├── finance_bot.py          ✅ (уже есть)
├── requirements.txt        ✅ (уже есть)
├── .env                    ❌ (создать вручную)
└── finance-key.json        ❌ (скачать из Google Cloud)
```

**Для Gmail парсера дополнительно:**

```
finance-bot/
├── gmail_parser.py         ✅ (уже есть)
├── credentials.json        ❌ (скачать из Google Cloud)
└── token.json              ⚙️ (создастся автоматически)
```

---

## 🔍 КАК ПРОВЕРИТЬ ЧТО ВСЁ НА МЕСТЕ?

### Проверка 1: Все ли файлы есть?

```bash
cd finance-bot

# Проверка основных файлов
ls -lh finance_bot.py gmail_parser.py requirements.txt

# Проверка конфигурации
ls -lh .env finance-key.json credentials.json

# Если какого-то файла нет — создайте по инструкции
```

### Проверка 2: Правильно ли заполнен .env?

```bash
cat .env | grep -v "^#" | grep -v "^$"

# Должно быть примерно так:
# TELEGRAM_TOKEN=123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
# ADMIN_TELEGRAM_ID=123456789
# ALLOWED_USER_IDS=123456789
# SHEET_URL=https://docs.google.com/spreadsheets/d/...
# WEBHOOK_URL=http://localhost:5000/webhook/transaction
```

### Проверка 3: Валидны ли JSON ключи?

```bash
# Проверка finance-key.json
python -c "import json; json.load(open('finance-key.json')); print('✅ finance-key.json валиден')"

# Проверка credentials.json
python -c "import json; json.load(open('credentials.json')); print('✅ credentials.json валиден')"
```

---

## 🎯 БЫСТРЫЙ СТАРТ (пошаговый план)

### Этап 1: Скачайте готовые файлы ✅

Скачайте все файлы которые я создал (см. выше).

### Этап 2: Создайте .env файл ⏳

```bash
cp .env.example .env
nano .env
# Заполните все переменные
```

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Разделы 1-2

### Этап 3: Получите Google Sheets API ключ ⏳

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Раздел 3

### Этап 4: Получите Gmail API ключ ⏳

**📖 Инструкция:** [HOW_TO_GET_KEYS.md](#) → Раздел 4

### Этап 5: Установите зависимости ⏳

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Этап 6: Запустите бота ⏳

```bash
python finance_bot.py
```

### Этап 7: (Опционально) Запустите Gmail парсер ⏳

```bash
# В отдельном терминале
python gmail_parser.py
```

---

## 📊 РАЗМЕРЫ ФАЙЛОВ

```
finance_bot.py              22 KB   (основной бот)
gmail_parser.py              8 KB   (email парсер)
requirements.txt           213 B   (зависимости)
README.md                   13 KB   (описание)
DEPLOYMENT.md               16 KB   (инструкция по развёртыванию)
HOW_TO_GET_KEYS.md          15 KB   (как получить ключи)
TABLE_ANALYSIS.md           17 KB   (анализ таблицы)
iPhone_Shortcuts_Setup.md    9 KB   (iOS автоматизация)
.env                       ~500 B   (конфигурация)
finance-key.json           ~2 KB   (Google Sheets ключ)
credentials.json           ~600 B   (Gmail ключ)
token.json                 ~200 B   (Gmail токен, создаётся автоматически)

ИТОГО: ~103 KB (без виртуального окружения)
```

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

### 1. Безопасность

**НИКОГДА не публикуйте эти файлы:**
- `.env`
- `finance-key.json`
- `credentials.json`
- `token.json`

Если случайно опубликовали:
1. Немедленно удалите репозиторий
2. Отзовите ключи в Google Cloud Console
3. Создайте новые ключи

### 2. Бэкап

Делайте регулярные бэкапы:
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz *.py *.json .env
```

### 3. Git

Если используете Git, убедитесь что `.gitignore` на месте:
```bash
cat .gitignore

# Должно быть:
.env
finance-key.json
credentials.json
token.json
```

---

## 📞 ПОДДЕРЖКА

Если что-то не работает:
1. Проверьте, что все 4 файла созданы (`.env`, `finance-key.json`, `credentials.json`, `token.json`)
2. Проверьте логи: `journalctl -u finance-bot -f`
3. Запустите проверки из [HOW_TO_GET_KEYS.md](#) → Раздел 5
4. Читайте [DEPLOYMENT.md](#) → Troubleshooting

**Удачи!** 🚀

# -*- coding: utf-8 -*-
import os
import logging
import base64
from datetime import datetime
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from flask import Flask, request, jsonify
import threading
import requests
import json
import uuid
import xml.etree.ElementTree as ET

pending_transactions = {}
pdf_sessions = {}
saved_drafts = {}  # user_id -> list of draft transactions

# === Настройка ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHEET_URL = os.getenv("SHEET_URL")
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")
ALLOWED_IDS = set(int(x.strip()) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip())
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)

# === Подключение к Google Таблице ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("finance-key.json", scope)
gc = gspread.authorize(creds)
sh = gc.open_by_url(SHEET_URL)

# === КУРС ЦБ РФ ===
def get_cbr_rate(currency: str) -> float:
    if currency == "RUB":
        return 1.0
    try:
        response = requests.get("https://www.cbr.ru/scripts/XML_daily.asp", timeout=5)
        root = ET.fromstring(response.content)
        for valute in root.findall('Valute'):
            char_code = valute.find('CharCode').text
            if char_code == currency:
                value = valute.find('Value').text.replace(',', '.')
                nominal = int(valute.find('Nominal').text)
                return float(value) / nominal
    except Exception as e:
        logging.error(f"Ошибка получения курса ЦБ: {e}")
    return 1.0

# === GEMINI API ===
def ask_gemini(prompt: str, pdf_base64: str = None) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    parts = []
    if pdf_base64:
        parts.append({"inline_data": {"mime_type": "application/pdf", "data": pdf_base64}})
    parts.append({"text": prompt})
    body = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.1}}
    response = requests.post(url, json=body, timeout=60)
    data = response.json()
    if "candidates" not in data:
        logging.error(f"Gemini error response: {json.dumps(data, ensure_ascii=False)[:500]}")
        raise ValueError(f"Gemini API error: {data.get('error', {}).get('message', str(data))}")
    return data["candidates"][0]["content"]["parts"][0]["text"]

# === УГАДАТЬ КАТЕГОРИЮ ===
def guess_category(merchant: str, amount: float) -> tuple:
    subcategories_str = json.dumps(CATEGORIES, ensure_ascii=False)
    prompt = f"""Определи категорию и подкатегорию транзакции.

Место/магазин: {merchant}
Сумма: {amount}

Доступные категории и подкатегории:
{subcategories_str}

Ответь ТОЛЬКО в формате JSON без markdown:
{{"category": "название категории", "subcategory": "название подкатегории или пустая строка"}}

Выбирай ТОЛЬКО из предложенных категорий и подкатегорий."""
    try:
        result = ask_gemini(prompt)
        result = result.strip().replace('```json', '').replace('```', '').strip()
        data = json.loads(result)
        category = data.get("category", "Прочее")
        subcategory = data.get("subcategory", "")
        if category not in CATEGORIES:
            category = "Прочее"
        if subcategory and subcategory not in CATEGORIES.get(category, []):
            subcategory = ""
        return category, subcategory
    except Exception as e:
        logging.error(f"Ошибка угадывания категории: {e}")
        return "Прочее", ""

# === ПАРСИНГ PDF ===
def parse_pdf_transactions(pdf_base64: str) -> list:
    prompt = """Извлеки все транзакции расходов из этой банковской выписки.

Для каждой транзакции верни:
- date: дата в формате ДД.ММ.ГГГГ
- amount: сумма числом (положительное)
- currency: валюта (RUB/USD/EUR/KZT)
- merchant: название места/магазина
- card: название карты или счёта если указано, иначе пустая строка

Игнорируй: пополнения, переводы между своими счетами, начисления процентов.

Ответь ТОЛЬКО в формате JSON массива без markdown:
[{"date": "...", "amount": 0.0, "currency": "RUB", "merchant": "...", "card": ""}]

Если транзакций нет — верни пустой массив []."""
    try:
        result = ask_gemini(prompt, pdf_base64)
        result = result.strip().replace('```json', '').replace('```', '').strip()
        transactions = json.loads(result)
        return transactions if isinstance(transactions, list) else []
    except Exception as e:
        logging.error(f"Ошибка парсинга PDF: {e}")
        return []

# === ПРОВЕРКА ДУБЛИКАТОВ ===
def get_existing_transactions() -> set:
    try:
        ws = sh.worksheet("Транзакции")
        records = ws.get_all_records()
        existing = set()
        for rec in records:
            date = str(rec.get('Дата', '')).split(',')[0].strip()
            amount = str(rec.get('Сумма', ''))
            merchant = str(rec.get('Место', '')).strip().lower()
            existing.add(f"{date}|{amount}|{merchant}")
        return existing
    except Exception as e:
        logging.error(f"Ошибка получения транзакций: {e}")
        return set()

# === КАТЕГОРИИ ===
CATEGORIES = {
    "Жизнь": ["Продукты", "Дети", "Джулиан (собака)", "Лана (жена)", "Образование", "Рестораны", "Одежда", "Гаджеты", "Подарки"],
    "Дом": ["Аренда", "Коммуналка", "Быт.товары"],
    "Транспорт": ["Такси", "Авто"],
    "Развлечения": [],
    "Здоровье": ["Спорт", "Гигиена/Красота", "Медицина", "Релакс"],
    "Путешествия": ["Авиа/ржд", "Отели"],
    "Прочее": ["Налоги, штрафы, комиссии"],
    "Крупные покупки": ["Жизнь", "Дом", "Здоровье", "Транспорт", "Прочее"],
    "Консалтинг": ["Ассистент", "Маркетинг", "Мероприятия", "Обучение", "Упаковка", "Гаджеты", "Подписки", "Прочее"],
    "Движение активов": ["Портфель Екатерины", "Портфель Влада", "Портфель Ланы (подушка)", "Пенсионный план", "Инвестиции в бизнес"]
}


INCOME_CATEGORIES = {
    "Зарплата": [],
    "Консалтинг": ["Ретейнеры", "Проекты", "Прочее"],
    "Дивиденды": [],
    "Прочее": [],
    "Подарки": [],
}
CURRENCIES = ["RUB", "USD", "EUR", "KZT"]
CARDS = ["Тинькофф", "Альфа", "Сбер", "Freedom"]
CURRENCY_SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}

# === Инициализация бота ===
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# === Состояния FSM ===
class TransactionForm(StatesGroup):
    waiting_for_action = State()
    tx_type = State()
    category = State()
    subcategory = State()
    amount = State()
    currency = State()
    date = State()
    card = State()
    comment = State()
    final_confirmation = State()

class PDFForm(StatesGroup):
    reviewing = State()

# === КЛАВИАТУРЫ ===
def main_menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Новая транзакция")
    kb.add("📋 Мои транзакции")
    kb.add("📊 Статистика")
    kb.add("⚙️ Настройки")
    kb.add("📥 Отложенные")
    return kb


def tx_type_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("💸 Расход", "💰 Доход")
    kb.add("⏪ Назад")
    return kb

def categories_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in CATEGORIES.keys():
        kb.add(cat)
    kb.add("⏪ Назад")
    return kb

def subcategories_kb(category):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    subs = CATEGORIES.get(category, [])
    for sub in subs:
        kb.add(sub)
    if not subs:
        kb.add("Без подкатегории")
    kb.add("⏪ Назад")
    return kb


def subcategories_kb_income(category):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    subs = INCOME_CATEGORIES.get(category, [])
    for sub in subs:
        kb.add(sub)
    if not subs:
        kb.add("Без подкатегории")
    kb.add("⏪ Назад")
    return kb

def currencies_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(*CURRENCIES)
    kb.add("⏪ Назад")
    return kb

def cards_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for card in CARDS:
        kb.add(card)
    kb.add("Пропустить")
    kb.add("⏪ Назад")
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("⏪ Назад")
    return kb

def skip_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Пропустить")
    kb.add("⏪ Назад")
    return kb

def confirmation_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("✅ Записать")
    kb.add("✏️ Изменить")
    kb.add("❌ Отменить")
    return kb

def pdf_action_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Записать все", callback_data="pdf|all"),
        types.InlineKeyboardButton("👀 Просмотреть", callback_data="pdf|review"),
    )
    kb.add(types.InlineKeyboardButton("❌ Отменить", callback_data="pdf|cancel"))
    return kb

def pdf_item_kb(idx: int, total: int):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("✅ Записать", callback_data=f"pdfi|save|{idx}"),
        types.InlineKeyboardButton("✏️ Изменить", callback_data=f"pdfi|edit|{idx}"),
        types.InlineKeyboardButton("⏭ Пропустить", callback_data=f"pdfi|skip|{idx}"),
    )
    if idx + 1 < total:
        kb.add(types.InlineKeyboardButton(f"Следующая → ({idx+2}/{total})", callback_data=f"pdfi|next|{idx}"))
    else:
        kb.add(types.InlineKeyboardButton("🏁 Завершить", callback_data="pdfi|done|0"))
    return kb

# === ПРЕВЬЮ ===
def build_preview(data: dict) -> str:
    currency = data.get('currency', 'RUB')
    amount = data.get('amount', 0)
    rate = data.get('rate', 1.0)
    amount_rub = data.get('amount_rub', amount)
    symbol = CURRENCY_SYMBOLS.get(currency, currency)

    tx_type_label = "💰 Доход" if data.get('tx_type') == 'Доход' else "💸 Расход"
    preview = (
        f"📝 <b>Предварительный просмотр:</b>\n\n"
        f"{tx_type_label}\n"
        f"📅 Дата: <code>{data.get('date', '')}</code>\n"
        f"📂 Категория: <code>{data.get('category', '')}</code>\n"
    )
    if data.get('subcategory'):
        preview += f"📁 Подкатегория: <code>{data['subcategory']}</code>\n"
    if currency == "RUB":
        preview += f"💰 Сумма: <code>{float(amount):,.0f}</code> ₽\n"
    else:
        preview += (
            f"💰 Сумма: <code>{float(amount):,.0f}</code> {symbol}\n"
            f"💱 Курс ЦБ: <code>{float(rate):,.4f}</code> ₽/{symbol}\n"
            f"🔄 В рублях: <code>{float(amount_rub):,.0f}</code> ₽\n"
        )
    if data.get('card'):
        preview += f"💳 Карта: <code>{data['card']}</code>\n"
    if data.get('comment'):
        preview += f"🏪 Место: <code>{data['comment']}</code>\n"
    return preview

def build_pdf_tx_preview(tx: dict, idx: int, total: int) -> str:
    currency = tx.get('currency', 'RUB')
    amount = tx.get('amount', 0)
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    category = tx.get('category', 'Прочее')
    subcategory = tx.get('subcategory', '')

    text = (
        f"<b>#{idx+1} из {total}</b>\n\n"
        f"🏪 <b>{tx.get('merchant', '')}</b>\n"
        f"💰 {float(amount):,.2f} {symbol}\n"
        f"📅 {tx.get('date', '')}\n"
        f"💳 {tx.get('card', '—') or '—'}\n"
        f"📂 {category}"
    )
    if subcategory:
        text += f" → {subcategory}"
    if tx.get('is_duplicate'):
        text += "\n\n⚠️ <i>Возможно уже записана</i>"
    return text

# === ЗАПИСЬ В SHEETS ===
async def save_transaction_to_sheets(data: dict):
    ws = sh.worksheet("Транзакции")
    currency = data.get('currency', 'RUB')
    amount = data.get('amount', 0)
    rate = data.get('rate', 1.0)
    amount_rub = data.get('amount_rub', amount)
    new_row = [
        data.get('date', ''),
        data.get('category', ''),
        data.get('subcategory', ''),
        amount,
        currency,
        rate if currency != 'RUB' else '',
        amount_rub,
        data.get('card', ''),
        data.get('comment', '')
        data.get('tx_type', 'Расход')
    ]
    ws.append_row(new_row)

# === УВЕДОМЛЕНИЕ АДМИНУ ===
async def notify_admin(message_text: str, user: types.User = None):
    if not ADMIN_ID:
        return
    user_info = ""
    if user:
        username = f"@{user.username}" if user.username else ""
        user_info = f"\n👤 {user.full_name} {username} (ID: {user.id})"
    try:
        await bot.send_message(ADMIN_ID, f"🔔 <b>Новая транзакция</b>\n{message_text}{user_info}", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка уведомления админу: {e}")

# === /start ===
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    if ALLOWED_IDS and message.from_user.id not in ALLOWED_IDS:
        await message.answer("🔒 У вас нет доступа к этому боту.")
        return
    await state.finish()
    await TransactionForm.waiting_for_action.set()
    await message.answer(
        "👋 <b>Добро пожаловать в DizelFinance!</b>\n\n"
        "📱 <b>Способы записи транзакций:</b>\n"
        "— Shortcut на iPhone → мгновенная запись\n"
        "— Отправь PDF выписку → автопарсинг\n"
        "— «➕ Новая транзакция» → ручной ввод\n\n"
        "Выберите действие:",
        parse_mode="HTML", reply_markup=main_menu_kb()
    )

# === ОБРАБОТКА PDF ===
@dp.message_handler(content_types=types.ContentType.DOCUMENT, state="*")
async def handle_pdf(message: types.Message, state: FSMContext):
    if ALLOWED_IDS and message.from_user.id not in ALLOWED_IDS:
        return
    if not message.document.file_name.lower().endswith('.pdf'):
        await message.answer("Пожалуйста отправьте PDF файл.")
        return

    await message.answer("⏳ Скачиваю и читаю выписку...")
    try:
        file = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file.file_path)
        pdf_base64 = base64.b64encode(file_bytes.read()).decode('utf-8')

        await message.answer("🤖 Claude анализирует транзакции...")
        transactions = parse_pdf_transactions(pdf_base64)

        if not transactions:
            await message.answer("❌ Не удалось найти транзакции в файле.")
            return

        existing = get_existing_transactions()
        await message.answer(f"📊 Найдено {len(transactions)} транзакций. Определяю категории...")

        enriched = []
        for tx in transactions:
            date_part = str(tx.get('date', '')).split(',')[0].strip()
            amount_str = str(tx.get('amount', ''))
            merchant = str(tx.get('merchant', '')).strip().lower()
            is_duplicate = f"{date_part}|{amount_str}|{merchant}" in existing

            category, subcategory = guess_category(tx.get('merchant', ''), tx.get('amount', 0))
            currency = tx.get('currency', 'RUB')
            rate = get_cbr_rate(currency)
            amount_rub = round(float(tx.get('amount', 0)) * rate, 2)

            enriched.append({
                **tx,
                'category': category,
                'subcategory': subcategory,
                'rate': rate,
                'amount_rub': amount_rub,
                'is_duplicate': is_duplicate
            })

        user_id = message.from_user.id
        pdf_sessions[user_id] = {
            'transactions': enriched,
            'current_idx': 0,
            'saved_count': 0,
            'skipped_count': 0
        }

        duplicate_count = sum(1 for t in enriched if t['is_duplicate'])
        new_count = len(enriched) - duplicate_count

        await message.answer(
            f"✅ <b>Анализ завершён!</b>\n\n"
            f"📄 Всего транзакций: {len(enriched)}\n"
            f"🆕 Новых: {new_count}\n"
            f"⚠️ Возможных дубликатов: {duplicate_count}\n\n"
            f"Что делаем?",
            parse_mode="HTML", reply_markup=pdf_action_kb()
        )

    except Exception as e:
        logging.error(f"Ошибка обработки PDF: {e}")
        await message.answer(f"❌ Ошибка при обработке PDF: {e}")

# === PDF — ДЕЙСТВИЯ (Записать все / Просмотреть / Отменить) ===
@dp.callback_query_handler(lambda c: c.data.startswith("pdf|"), state="*")
async def pdf_action_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    action = callback.data.split("|")[1]
    session = pdf_sessions.get(user_id)

    if not session:
        await callback.message.edit_text("❌ Сессия устарела. Загрузите PDF заново.")
        return

    if action == "cancel":
        pdf_sessions.pop(user_id, None)
        await callback.message.edit_text("❌ Отменено.")
        await callback.message.answer("Выберите действие:", reply_markup=main_menu_kb())

    elif action == "all":
        await callback.message.edit_text("⏳ Записываю все транзакции...")
        saved = 0
        for tx in session['transactions']:
            try:
                await save_transaction_to_sheets({
                    'date': tx.get('date', ''),
                    'category': tx.get('category', 'Прочее'),
                    'subcategory': tx.get('subcategory', ''),
                    'amount': tx.get('amount', 0),
                    'currency': tx.get('currency', 'RUB'),
                    'rate': tx.get('rate', 1.0),
                    'amount_rub': tx.get('amount_rub', tx.get('amount', 0)),
                    'card': tx.get('card', ''),
                    'comment': tx.get('merchant', '')
                })
                saved += 1
            except Exception as e:
                logging.error(f"Ошибка записи: {e}")
        pdf_sessions.pop(user_id, None)
        await callback.message.answer(f"✅ Записано {saved} транзакций!", reply_markup=main_menu_kb())

    elif action == "review":
        session['current_idx'] = 0
        await PDFForm.reviewing.set()
        await callback.message.edit_text("👀 Просматриваем по одной...")
        await show_pdf_transaction(callback.message, user_id, 0)

    await callback.answer()

# === ПОКАЗАТЬ ТРАНЗАКЦИЮ ===
async def show_pdf_transaction(message: types.Message, user_id: int, idx: int):
    session = pdf_sessions.get(user_id)
    if not session:
        return
    transactions = session['transactions']
    if idx >= len(transactions):
        saved = session.get('saved_count', 0)
        skipped = session.get('skipped_count', 0)
        pdf_sessions.pop(user_id, None)
        await message.answer(
            f"🏁 <b>Готово!</b>\n\n✅ Записано: {saved}\n⏭ Пропущено: {skipped}",
            parse_mode="HTML", reply_markup=main_menu_kb()
        )
        return
    tx = transactions[idx]
    text = build_pdf_tx_preview(tx, idx, len(transactions))
    await message.answer(text, parse_mode="HTML", reply_markup=pdf_item_kb(idx, len(transactions)))

# === PDF — КНОПКИ ПО ОДНОЙ ===
@dp.callback_query_handler(lambda c: c.data.startswith("pdfi|"), state="*")
async def pdf_item_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    parts = callback.data.split("|")
    action = parts[1]
    idx = int(parts[2])

    session = pdf_sessions.get(user_id)
    if not session:
        await callback.message.edit_text("❌ Сессия устарела.")
        return

    transactions = session['transactions']

    if action == "done":
        saved = session.get('saved_count', 0)
        skipped = session.get('skipped_count', 0)
        pdf_sessions.pop(user_id, None)
        await callback.message.edit_text(
            f"🏁 <b>Готово!</b>\n\n✅ Записано: {saved}\n⏭ Пропущено: {skipped}",
            parse_mode="HTML"
        )
        await callback.message.answer("Выберите действие:", reply_markup=main_menu_kb())
        await state.finish()

    elif action == "save":
        tx = transactions[idx]
        try:
            await save_transaction_to_sheets({
                'date': tx.get('date', ''),
                'category': tx.get('category', 'Прочее'),
                'subcategory': tx.get('subcategory', ''),
                'amount': tx.get('amount', 0),
                'currency': tx.get('currency', 'RUB'),
                'rate': tx.get('rate', 1.0),
                'amount_rub': tx.get('amount_rub', tx.get('amount', 0)),
                'card': tx.get('card', ''),
                'comment': tx.get('merchant', '')
            })
            session['saved_count'] = session.get('saved_count', 0) + 1
            await callback.answer("✅ Записано!")
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {e}")
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_pdf_transaction(callback.message, user_id, idx + 1)

    elif action == "skip":
        session['skipped_count'] = session.get('skipped_count', 0) + 1
        await callback.answer("⏭ Пропущено")
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_pdf_transaction(callback.message, user_id, idx + 1)

    elif action == "next":
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_pdf_transaction(callback.message, user_id, idx + 1)

    elif action == "edit":
        tx = transactions[idx]
        await state.update_data(
            amount=float(tx.get('amount', 0)),
            currency=tx.get('currency', 'RUB'),
            rate=tx.get('rate', 1.0),
            amount_rub=tx.get('amount_rub', tx.get('amount', 0)),
            card=tx.get('card', ''),
            date=tx.get('date', ''),
            comment=tx.get('merchant', ''),
            from_pdf=True,
            pdf_idx=idx
        )
        await callback.message.edit_reply_markup(reply_markup=None)
        await TransactionForm.category.set()
        await callback.message.answer(
            f"✏️ Редактируем #{idx+1}. Выберите категорию:",
            reply_markup=categories_kb()
        )

    await callback.answer()

# === ГЛАВНОЕ МЕНЮ ===
@dp.message_handler(lambda m: m.text == "➕ Новая транзакция", state="*")
async def new_transaction(message: types.Message, state: FSMContext):
    await state.finish()
    await TransactionForm.tx_type.set()
    await message.answer("Тип операции:", reply_markup=tx_type_kb())

# === ТИП ОПЕРАЦИИ ===
@dp.message_handler(state=TransactionForm.tx_type)
async def process_tx_type(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.waiting_for_action.set()
        await message.answer("Выберите действие:", reply_markup=main_menu_kb())
        return
    if message.text not in ["💸 Расход", "💰 Доход"]:
        await message.answer("Выберите тип:", reply_markup=tx_type_kb())
        return
    tx_type = "Расход" if message.text == "💸 Расход" else "Доход"
    await state.update_data(tx_type=tx_type)
    if tx_type == "Доход":
        await TransactionForm.category.set()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for cat in INCOME_CATEGORIES.keys():
            kb.add(cat)
        kb.add("⏪ Назад")
        await message.answer("Категория дохода:", reply_markup=kb)
    else:
        await TransactionForm.category.set()
        await message.answer("Категория расхода:", reply_markup=categories_kb())

# === КАТЕГОРИЯ ===
@dp.message_handler(state=TransactionForm.category)
async def process_category(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        # Restore draft if came from webhook
        data = await state.get_data()
        if data.get('from_webhook') and data.get('amount'):
            user_id = message.from_user.id
            if user_id not in saved_drafts:
                saved_drafts[user_id] = []
            import uuid as _uuid
            saved_drafts[user_id].append({
                "id": str(_uuid.uuid4())[:8],
                "a": data['amount'], "m": data.get('comment',''),
                "c": data.get('card',''), "d": data.get('date',''),
                "cur": data.get('currency','RUB'),
                "rate": data.get('rate', 1.0),
                "a_rub": data.get('amount_rub', data['amount'])
            })
        await TransactionForm.waiting_for_action.set()
        await message.answer("Выберите действие:", reply_markup=main_menu_kb())
        return
    if message.text not in CATEGORIES:
        await message.answer("Выберите категорию из списка:", reply_markup=categories_kb())
        return
    data_check = await state.get_data()
    tx_type = data_check.get('tx_type', 'Расход')
    cats = INCOME_CATEGORIES if tx_type == 'Доход' else CATEGORIES
    if message.text not in cats:
        await message.answer("Выберите из списка:", reply_markup=categories_kb() if tx_type == 'Расход' else tx_type_kb())
        return
    await state.update_data(category=message.text)
    subs = cats[message.text]
    if subs:
        await TransactionForm.subcategory.set()
        await message.answer(f"Выберите подкатегорию для '{message.text}':", reply_markup=subcategories_kb(message.text) if tx_type == 'Расход' else subcategories_kb_income(message.text))
    else:
        await state.update_data(subcategory="")
        data = await state.get_data()
        if data.get('from_webhook') or data.get('from_pdf'):
            await TransactionForm.final_confirmation.set()
            await message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())
        else:
            await TransactionForm.amount.set()
            await message.answer("Введите сумму:", reply_markup=back_kb())

# === ПОДКАТЕГОРИЯ ===
@dp.message_handler(state=TransactionForm.subcategory)
async def process_subcategory(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.category.set()
        await message.answer("Выберите категорию:", reply_markup=categories_kb())
        return
    data = await state.get_data()
    category = data.get("category")
    if message.text == "Без подкатегории":
        await state.update_data(subcategory="")
    elif message.text in CATEGORIES.get(category, []):
        await state.update_data(subcategory=message.text)
    else:
        await message.answer("Выберите подкатегорию из списка:", reply_markup=subcategories_kb(category))
        return
    data = await state.get_data()
    if data.get('from_webhook') or data.get('from_pdf'):
        await TransactionForm.final_confirmation.set()
        await message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())
    else:
        await TransactionForm.amount.set()
        await message.answer("Введите сумму:", reply_markup=back_kb())

# === СУММА ===
@dp.message_handler(state=TransactionForm.amount)
async def process_amount(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        data = await state.get_data()
        category = data.get("category")
        if CATEGORIES.get(category):
            await TransactionForm.subcategory.set()
            await message.answer("Выберите подкатегорию:", reply_markup=subcategories_kb(category))
        else:
            await TransactionForm.category.set()
            await message.answer("Выберите категорию:", reply_markup=categories_kb())
        return
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную сумму (например: 5000 или 5000.50):", reply_markup=back_kb())
        return
    await state.update_data(amount=amount)
    await TransactionForm.currency.set()
    await message.answer("Выберите валюту:", reply_markup=currencies_kb())

# === ВАЛЮТА ===
@dp.message_handler(state=TransactionForm.currency)
async def process_currency(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.amount.set()
        await message.answer("Введите сумму:", reply_markup=back_kb())
        return
    if message.text not in CURRENCIES:
        await message.answer("Выберите валюту из списка:", reply_markup=currencies_kb())
        return
    currency = message.text
    data = await state.get_data()
    rate = get_cbr_rate(currency)
    amount_rub = round(float(data.get('amount', 0)) * rate, 2)
    await state.update_data(currency=currency, rate=rate, amount_rub=amount_rub)
    await TransactionForm.date.set()
    today = datetime.now().strftime("%d.%m.%Y, %H:%M")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(today)
    kb.add("⏪ Назад")
    await message.answer("Введите дату и время или нажмите кнопку:", reply_markup=kb)

# === ДАТА ===
@dp.message_handler(state=TransactionForm.date)
async def process_date(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.currency.set()
        await message.answer("Выберите валюту:", reply_markup=currencies_kb())
        return
    date_str = message.text.strip()
    parsed = False
    for fmt in ("%d.%m.%Y, %H:%M", "%d.%m.%Y,%H:%M", "%d.%m.%Y"):
        try:
            datetime.strptime(date_str, fmt)
            parsed = True
            break
        except ValueError:
            continue
    if not parsed:
        await message.answer("Введите дату в формате ДД.ММ.ГГГГ, ЧЧ:ММ (например: 09.03.2026, 14:35):", reply_markup=back_kb())
        return
    await state.update_data(date=date_str)
    await TransactionForm.card.set()
    await message.answer("Выберите карту/счёт или пропустите:", reply_markup=cards_kb())

# === КАРТА ===
@dp.message_handler(state=TransactionForm.card)
async def process_card(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.date.set()
        today = datetime.now().strftime("%d.%m.%Y, %H:%M")
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(today)
        kb.add("⏪ Назад")
        await message.answer("Введите дату:", reply_markup=kb)
        return
    card = "" if message.text == "Пропустить" else message.text
    await state.update_data(card=card)
    await TransactionForm.comment.set()
    await message.answer("Введите место/магазин (или пропустите):", reply_markup=skip_kb())

# === МЕСТО ===
@dp.message_handler(state=TransactionForm.comment)
async def process_comment(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.card.set()
        await message.answer("Выберите карту/счёт:", reply_markup=cards_kb())
        return
    comment = "" if message.text == "Пропустить" else message.text
    await state.update_data(comment=comment)
    data = await state.get_data()
    await TransactionForm.final_confirmation.set()
    await message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())

# === ПОДТВЕРЖДЕНИЕ ===
@dp.message_handler(state=TransactionForm.final_confirmation)
async def final_confirmation(message: types.Message, state: FSMContext):
    if message.text == "✅ Записать":
        data = await state.get_data()
        try:
            await save_transaction_to_sheets(data)
            await notify_admin(
                f"Категория: {data.get('category', '')}\n"
                f"Сумма: {float(data.get('amount', 0)):,.2f} {data.get('currency', 'RUB')}\n"
                f"В рублях: {float(data.get('amount_rub', data.get('amount', 0))):,.2f} ₽",
                message.from_user
            )
            # Если редактировали из PDF — возвращаемся к следующей
            if data.get('from_pdf'):
                user_id = message.from_user.id
                session = pdf_sessions.get(user_id)
                if session:
                    session['saved_count'] = session.get('saved_count', 0) + 1
                    next_idx = data.get('pdf_idx', 0) + 1
                    session['current_idx'] = next_idx
                    await state.finish()
                    await PDFForm.reviewing.set()
                    await message.answer("✅ Записано!", reply_markup=types.ReplyKeyboardRemove())
                    await show_pdf_transaction(message, user_id, next_idx)
                    return
            await message.answer("✅ Транзакция записана!", reply_markup=main_menu_kb())
            await state.finish()
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")
            await message.answer(f"❌ Ошибка: {e}", reply_markup=main_menu_kb())
            await state.finish()
    elif message.text == "✏️ Изменить":
        await TransactionForm.category.set()
        await message.answer("Начнём заново. Выберите категорию:", reply_markup=categories_kb())
    elif message.text == "❌ Отменить":
        await state.finish()
        await message.answer("Операция отменена.", reply_markup=main_menu_kb())

# === МОИ ТРАНЗАКЦИИ ===
@dp.message_handler(lambda m: m.text == "📋 Мои транзакции", state="*")
async def my_transactions(message: types.Message):
    try:
        ws = sh.worksheet("Транзакции")
        records = ws.get_all_records()
        if not records:
            await message.answer("📂 Нет транзакций.", reply_markup=main_menu_kb())
            return
        last_10 = records[-10:]
        text = "📋 <b>Последние 10 транзакций:</b>\n\n"
        for rec in last_10:
            currency = str(rec.get('Валюта', 'RUB')).strip() or 'RUB'
            symbol = CURRENCY_SYMBOLS.get(currency, currency)
            try:
                amount = float(str(rec.get('Сумма', 0)).replace(',', '.').replace(' ', '') or 0)
            except:
                amount = 0
            try:
                raw_rub = rec.get('Сумма в Руб', rec.get('Сумма в RUB', ''))
                amount_rub = float(str(raw_rub).replace(',', '.').replace(' ', '') or amount)
            except:
                amount_rub = amount
            text += f"📅 {rec.get('Дата', '')}\n"
            text += f"📂 {rec.get('Категория', '')} → {rec.get('Подкатегория', '')}\n"
            text += f"💰 {amount:,.0f} {symbol}"
            if currency != 'RUB':
                text += f" ({amount_rub:,.0f} ₽)"
            text += f"\n🏪 {rec.get('Место', '')}\n{'─' * 30}\n"
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
    except Exception as e:
        logging.error(f"Ошибка чтения транзакций: {e}")
        await message.answer("❌ Ошибка при загрузке транзакций.", reply_markup=main_menu_kb())

# === СТАТИСТИКА ===
@dp.message_handler(lambda m: m.text == "📊 Статистика", state="*")
async def statistics(message: types.Message):
    try:
        ws = sh.worksheet("Транзакции")
        records = ws.get_all_records()
        if not records:
            await message.answer("📂 Нет данных для статистики.", reply_markup=main_menu_kb())
            return
        current_month = datetime.now().strftime("%m.%Y")
        category_totals = {}
        for rec in records:
            date_part = str(rec.get('Дата', '')).split(',')[0].strip()
            try:
                dt = datetime.strptime(date_part, "%d.%m.%Y")
                if dt.strftime("%m.%Y") == current_month:
                    cat = rec.get('Категория', 'Прочее')
                    raw = rec.get('Сумма в Руб', rec.get('Сумма в RUB', rec.get('Сумма', 0)))
                    amount_rub = float(str(raw).replace(',', '.').replace(' ', '') or 0)
                    category_totals[cat] = category_totals.get(cat, 0) + amount_rub
            except (ValueError, TypeError):
                continue
        if not category_totals:
            await message.answer("📂 Нет транзакций за текущий месяц.", reply_markup=main_menu_kb())
            return
        total = sum(category_totals.values())
        text = f"📊 <b>Статистика за {current_month}:</b>\n\n"
        for cat, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            percent = (amount / total) * 100
            text += f"📂 {cat}: {amount:,.0f} ₽ ({percent:.1f}%)\n"
        text += f"\n{'═' * 30}\n💰 <b>ИТОГО:</b> {total:,.0f} ₽"
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
    except Exception as e:
        logging.error(f"Ошибка статистики: {e}")
        await message.answer("❌ Ошибка при расчёте статистики.", reply_markup=main_menu_kb())

# === НАСТРОЙКИ ===
@dp.message_handler(lambda m: m.text == "⚙️ Настройки", state="*")
async def settings(message: types.Message):
    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"👤 Ваш ID: <code>{message.from_user.id}</code>\n"
        f"🗄 Google Sheets: {'✅ Подключён' if sh else '❌ Не подключён'}\n"
        f"🤖 Gemini API: {'✅ Подключён' if GEMINI_API_KEY else '❌ Не настроен'}",
        parse_mode="HTML", reply_markup=main_menu_kb()
    )


# === ОТЛОЖЕННЫЕ ТРАНЗАКЦИИ ===
@dp.message_handler(lambda m: m.text == "📥 Отложенные", state="*")
async def show_drafts(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    drafts = saved_drafts.get(user_id, [])
    if not drafts:
        await message.answer("📭 Нет отложенных транзакций.", reply_markup=main_menu_kb())
        return
    text = f"📥 <b>Отложенные транзакции ({len(drafts)}):</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, d in enumerate(drafts):
        symbol = CURRENCY_SYMBOLS.get(d['cur'], d['cur'])
        text += f"{i+1}. 💰 {d['a']:,.0f} {symbol} — {d['m']} ({d['d']})\n"
        kb.add(types.InlineKeyboardButton(
            f"✏️ #{i+1} {d['m']} {d['a']:,.0f} {symbol}",
            callback_data=f"draft|{d['id']}"
        ))
    kb.add(types.InlineKeyboardButton("🗑 Очистить все", callback_data="draft|clear"))
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("draft|"), state="*")
async def process_draft(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    action = callback.data.split("|")[1]
    
    if action == "clear":
        saved_drafts.pop(user_id, None)
        await callback.message.edit_text("🗑 Все черновики удалены.")
        await callback.answer()
        return
    
    draft_id = action
    drafts = saved_drafts.get(user_id, [])
    draft = next((d for d in drafts if d['id'] == draft_id), None)
    if not draft:
        await callback.message.edit_text("❌ Черновик не найден.")
        await callback.answer()
        return
    
    # Remove from drafts
    saved_drafts[user_id] = [d for d in drafts if d['id'] != draft_id]
    
    await state.update_data(
        amount=draft['a'],
        currency=draft['cur'],
        rate=draft['rate'],
        amount_rub=draft['a_rub'],
        card=draft['c'],
        date=draft['d'],
        comment=draft['m'],
        tx_type=draft.get('tx_type', 'Расход'),
        from_webhook=True
    )
    symbol = CURRENCY_SYMBOLS.get(draft['cur'], '₽')
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Продолжаем: {draft['a']:,.0f} {symbol} — {draft['m']}\n\nВыберите категорию:",
        reply_markup=categories_kb()
    )
    await TransactionForm.category.set()
    await callback.answer()

# === НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ===
@dp.message_handler(state="*")
async def unknown_message(message: types.Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Не понимаю. Используйте меню 👇", reply_markup=main_menu_kb())

# === ПАРСИНГ SMS ===
def parse_sms_transaction(sms_text: str) -> dict | None:
    """Парсит SMS от банка и извлекает данные транзакции"""
    prompt = f"""Извлеки данные транзакции из банковского SMS.

SMS: {sms_text}

Ответь ТОЛЬКО в формате JSON без markdown:
{{"amount": 0.0, "currency": "RUB", "merchant": "название места или описание", "card": "название карты или последние 4 цифры", "tx_type": "Расход или Доход", "date": "ДД.ММ.ГГГГ или пустая строка"}}

Правила:
- tx_type = "Доход" если это пополнение/зачисление/перевод ПОЛУЧЕН
- tx_type = "Расход" если это списание/покупка/оплата
- amount всегда положительное число
- если дата не указана — пустая строка
- если карта не определена — пустая строка

Если это НЕ банковское SMS с транзакцией — верни {{"error": "not_transaction"}}"""
    try:
        result = ask_gemini(prompt)
        result = result.strip().replace('```json', '').replace('```', '').strip()
        data = json.loads(result)
        if data.get('error') == 'not_transaction':
            return None
        return data
    except Exception as e:
        logging.error(f"Ошибка парсинга SMS: {e}")
        return None

# === WEBHOOK ===
app = Flask(__name__)

@app.route('/webhook/transaction', methods=['POST'])
def webhook_transaction():
    try:
        data = request.json
        user_id = data.get('user_id')
        if not user_id or (ALLOWED_IDS and int(user_id) not in ALLOWED_IDS):
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        amount = float(data.get('amount', 0))
        currency = data.get('currency', 'RUB')
        merchant = data.get('merchant', 'Неизвестно')
        card = data.get('card', 'Неизвестно')
        date = data.get('date', datetime.now().strftime('%d.%m.%Y, %H:%M'))

        rate = get_cbr_rate(currency)
        amount_rub = round(amount * rate, 2)
        symbol = CURRENCY_SYMBOLS.get(currency, currency)

        message_text = f"🔔 <b>Новая транзакция:</b>\n\n💰 Сумма: {amount:,.2f} {symbol}\n"
        if currency != 'RUB':
            message_text += f"🔄 В рублях: {amount_rub:,.2f} ₽\n"
        message_text += f"🏪 Место: {merchant}\n💳 Карта: {card}\n📅 Дата: {date}\n\nЗаписать?"

        tx_id = str(uuid.uuid4())[:8]
        tx_type_w = data.get('tx_type', 'Расход')
        pending_transactions[tx_id] = {
            "a": amount, "m": merchant, "c": card, "d": date,
            "cur": currency, "rate": rate, "a_rub": amount_rub,
            "tx_type": tx_type_w
        }
        # Автосохранение в черновики
        draft_id = str(uuid.uuid4())[:8]
        if int(user_id) not in saved_drafts:
            saved_drafts[int(user_id)] = []
        saved_drafts[int(user_id)].append({
            "id": draft_id, "a": amount, "m": merchant, "c": card, "d": date,
            "cur": currency, "rate": rate, "a_rub": amount_rub,
            "tx_type": tx_type_w
        })

        # Quick category buttons
        kb = types.InlineKeyboardMarkup(row_width=3)
        quick_cats = ["Жизнь", "Транспорт", "Дом", "Здоровье", "Развлечения", "Прочее"]
        for cat in quick_cats:
            kb.add(types.InlineKeyboardButton(cat, callback_data=f"wbq|{tx_id}|{cat}"))
        kb.add(
            types.InlineKeyboardButton("📋 Все категории", callback_data=f"wb|{tx_id}"),
            types.InlineKeyboardButton("❌ Пропустить", callback_data="wb|no")
        )

        import requests as req
        req.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": user_id,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": kb.to_python()
        })
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"Ошибка webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# === WEBHOOK SMS ===
@app.route('/webhook/sms', methods=['POST'])
def webhook_sms():
    try:
        data = request.json
        logging.info(f"SMS WEBHOOK: {data}")
        user_id = data.get('user_id')
        sms_text = data.get('sms', '').strip()

        if not user_id or not sms_text:
            return jsonify({"status": "error", "message": "Missing user_id or sms"}), 400
        if ALLOWED_IDS and int(user_id) not in ALLOWED_IDS:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        tx = parse_sms_transaction(sms_text)
        if not tx:
            return jsonify({"status": "skip", "message": "Not a transaction SMS"}), 200

        amount = float(tx.get('amount', 0))
        currency = tx.get('currency', 'RUB')
        merchant = tx.get('merchant', 'SMS')
        card = tx.get('card', '')
        tx_type_w = tx.get('tx_type', 'Расход')
        date = tx.get('date') or datetime.now().strftime('%d.%m.%Y, %H:%M')

        rate = get_cbr_rate(currency)
        amount_rub = round(amount * rate, 2)
        symbol = CURRENCY_SYMBOLS.get(currency, currency)
        tx_icon = "💰" if tx_type_w == 'Доход' else "💸"

        message_text = (
            f"📱 <b>SMS транзакция:</b>

"
            f"{tx_icon} {tx_type_w}
"
            f"💵 {amount:,.2f} {symbol}
"
        )
        if currency != 'RUB':
            message_text += f"🔄 В рублях: {amount_rub:,.2f} ₽
"
        message_text += f"🏪 {merchant}
💳 {card}
📅 {date}

Записать?"

        tx_id = str(uuid.uuid4())[:8]
        pending_transactions[tx_id] = {
            "a": amount, "m": merchant, "c": card, "d": date,
            "cur": currency, "rate": rate, "a_rub": amount_rub,
            "tx_type": tx_type_w,
        }
        draft_id = str(uuid.uuid4())[:8]
        if int(user_id) not in saved_drafts:
            saved_drafts[int(user_id)] = []
        saved_drafts[int(user_id)].append({
            "id": draft_id, "a": amount, "m": merchant, "c": card, "d": date,
            "cur": currency, "rate": rate, "a_rub": amount_rub,
            "tx_type": tx_type_w,
        })

        kb = types.InlineKeyboardMarkup(row_width=3)
        quick_cats = ["Жизнь", "Транспорт", "Дом", "Здоровье", "Развлечения", "Прочее"]
        for cat in quick_cats:
            kb.add(types.InlineKeyboardButton(cat, callback_data=f"wbq|{tx_id}|{cat}"))
        kb.add(
            types.InlineKeyboardButton("📋 Все категории", callback_data=f"wb|{tx_id}"),
            types.InlineKeyboardButton("❌ Пропустить", callback_data="wb|no")
        )

        import requests as req
        req.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": user_id, "text": message_text, "parse_mode": "HTML",
            "reply_markup": kb.to_python()
        })
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"Ошибка SMS webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# === ОБРАБОТКА SMS ТЕКСТОМ В БОТЕ ===
@dp.message_handler(lambda m: m.text and len(m.text) > 20 and any(w in m.text.lower() for w in ['списано', 'зачислено', 'покупка', 'оплата', 'перевод', 'баланс', 'карта']), state=TransactionForm.waiting_for_action)
async def handle_sms_text(message: types.Message, state: FSMContext):
    """Обрабатывает SMS вставленный текстом в бот"""
    if ALLOWED_IDS and message.from_user.id not in ALLOWED_IDS:
        return
    await message.answer("📱 Похоже на банковское SMS, разбираю...")
    tx = parse_sms_transaction(message.text)
    if not tx:
        await message.answer("❌ Не смог распознать транзакцию. Попробуйте ➕ Новая транзакция.")
        return

    amount = float(tx.get('amount', 0))
    currency = tx.get('currency', 'RUB')
    merchant = tx.get('merchant', 'SMS')
    card = tx.get('card', '')
    tx_type_w = tx.get('tx_type', 'Расход')
    date = tx.get('date') or datetime.now().strftime('%d.%m.%Y, %H:%M')

    rate = get_cbr_rate(currency)
    amount_rub = round(amount * rate, 2)
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    tx_icon = "💰" if tx_type_w == 'Доход' else "💸"

    tx_id = str(uuid.uuid4())[:8]
    pending_transactions[tx_id] = {
        "a": amount, "m": merchant, "c": card, "d": date,
        "cur": currency, "rate": rate, "a_rub": amount_rub,
        "tx_type": tx_type_w,
    }
    user_id = message.from_user.id
    if user_id not in saved_drafts:
        saved_drafts[user_id] = []
    saved_drafts[user_id].append({
        "id": str(uuid.uuid4())[:8], "a": amount, "m": merchant, "c": card, "d": date,
        "cur": currency, "rate": rate, "a_rub": amount_rub, "tx_type": tx_type_w,
    })

    kb = types.InlineKeyboardMarkup(row_width=3)
    quick_cats = ["Жизнь", "Транспорт", "Дом", "Здоровье", "Развлечения", "Прочее"]
    for cat in quick_cats:
        kb.add(types.InlineKeyboardButton(cat, callback_data=f"wbq|{tx_id}|{cat}"))
    kb.add(
        types.InlineKeyboardButton("📋 Все категории", callback_data=f"wb|{tx_id}"),
        types.InlineKeyboardButton("❌ Пропустить", callback_data="wb|no")
    )

    preview = f"📱 <b>SMS распознано:</b>

{tx_icon} {tx_type_w}
💵 {amount:,.2f} {symbol}"
    if currency != 'RUB':
        preview += f"
🔄 {amount_rub:,.2f} ₽"
    preview += f"
🏪 {merchant}
💳 {card}
📅 {date}

Выберите категорию:"
    await message.answer(preview, parse_mode="HTML", reply_markup=kb)

# === WEBHOOK БЫСТРЫЕ КАТЕГОРИИ ===
@dp.callback_query_handler(lambda c: c.data.startswith("wbq|"), state="*")
async def process_webhook_quick(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("|")
    tx_id = parts[1]
    category = parts[2]
    
    tx = pending_transactions.pop(tx_id, None)
    if not tx:
        await callback.message.edit_text("❌ Транзакция устарела.")
        await callback.answer()
        return
    
    # Remove from drafts
    user_id = callback.from_user.id
    if user_id in saved_drafts:
        saved_drafts[user_id] = [d for d in saved_drafts[user_id]
                                  if not (d['a'] == tx['a'] and d['m'] == tx['m'] and d['d'] == tx['d'])]
    
    await state.update_data(
        amount=tx['a'], currency=tx['cur'], rate=tx['rate'],
        amount_rub=tx['a_rub'], card=tx['c'], date=tx['d'],
        comment=tx['m'], from_webhook=True, category=category,
        tx_type=tx.get('tx_type', 'Расход')
    )
    
    subs = CATEGORIES.get(category, [])
    await callback.message.edit_reply_markup(reply_markup=None)
    
    if subs:
        await TransactionForm.subcategory.set()
        kb = types.InlineKeyboardMarkup(row_width=2)
        for sub in subs:
            kb.add(types.InlineKeyboardButton(sub, callback_data=f"wbs|{sub}"))
        kb.add(types.InlineKeyboardButton("Без подкатегории", callback_data="wbs|none"))
        symbol = CURRENCY_SYMBOLS.get(tx['cur'], tx['cur'])
        await callback.message.answer(
            f"📂 {category} — {tx['a']:,.0f} {symbol} — {tx['m']}\n\nПодкатегория:",
            reply_markup=kb
        )
    else:
        await state.update_data(subcategory="")
        data = await state.get_data()
        await TransactionForm.final_confirmation.set()
        await callback.message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("wbs|"), state=TransactionForm.subcategory)
async def process_webhook_sub(callback: types.CallbackQuery, state: FSMContext):
    sub = callback.data.split("|")[1]
    await state.update_data(subcategory="" if sub == "none" else sub)
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await TransactionForm.final_confirmation.set()
    await callback.message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())
    await callback.answer()

# === WEBHOOK КНОПКИ ===
@dp.callback_query_handler(lambda c: c.data.startswith("wb|"), state="*")
async def process_webhook_callback(callback: types.CallbackQuery, state: FSMContext):
    payload = callback.data[3:]
    if payload == "no":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("❌ Пропущено.")
        await callback.answer()
        return
    tx = pending_transactions.pop(payload, None)
    if not tx:
        await callback.message.edit_text("❌ Транзакция устарела.")
        return
    # Удаляем из черновиков если там есть
    user_id_cb = callback.from_user.id
    if user_id_cb in saved_drafts:
        saved_drafts[user_id_cb] = [d for d in saved_drafts[user_id_cb] 
                                     if not (d['a'] == tx['a'] and d['m'] == tx['m'] and d['d'] == tx['d'])]
    await state.update_data(
        amount=tx.get('a', 0),
        currency=tx.get('cur', 'RUB'),
        rate=tx.get('rate', 1.0),
        amount_rub=tx.get('a_rub', tx.get('a', 0)),
        card=tx.get('c', ''),
        date=tx.get('d', datetime.now().strftime('%d.%m.%Y, %H:%M')),
        comment=tx.get('m', ''),
        tx_type=tx.get('tx_type', 'Расход'),
        from_webhook=True
    )
    symbol = CURRENCY_SYMBOLS.get(tx.get('cur', 'RUB'), '₽')
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Записываем: {tx.get('a')} {symbol} — {tx.get('m', '')}\n\nВыберите категорию:",
        reply_markup=categories_kb()
    )
    await TransactionForm.category.set()
    await callback.answer()

# === ЗАПУСК ===
def run_bot():
    executor.start_polling(dp, skip_updates=True)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("🚀 DizelFinance Bot запущен!")
    run_bot()
# -*- coding: utf-8 -*-
import os
import logging
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
import json
import requests
import uuid
import xml.etree.ElementTree as ET

pending_transactions = {}

# === Настройка ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHEET_URL = os.getenv("SHEET_URL")
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")
ALLOWED_IDS = set(int(x.strip()) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip())

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

# === КАТЕГОРИИ И ПОДКАТЕГОРИИ ===
CATEGORIES = {
    "Жизнь": [
        "Продукты",
        "Дети",
        "Джулиан (собака)",
        "Лана (жена)",
        "Образование",
        "Рестораны",
        "Одежда",
        "Гаджеты",
        "Подарки"
    ],
    "Дом": [
        "Аренда",
        "Коммуналка",
        "Быт.товары"
    ],
    "Транспорт": [
        "Такси",
        "Авто"
    ],
    "Развлечения": [],
    "Здоровье": [
        "Спорт",
        "Гигиена/Красота",
        "Медицина",
        "Релакс"
    ],
    "Путешествия": [
        "Авиа/ржд",
        "Отели"
    ],
    "Прочее": [
        "Налоги, штрафы, комиссии"
    ],
    "Крупные покупки": [
        "Жизнь",
        "Дом",
        "Здоровье",
        "Транспорт",
        "Прочее"
    ],
    "Консалтинг": [
        "Ассистент",
        "Маркетинг",
        "Мероприятия",
        "Обучение",
        "Упаковка",
        "Гаджеты",
        "Подписки",
        "Прочее"
    ],
    "Движение активов": [
        "Портфель Екатерины",
        "Портфель Влада",
        "Портфель Ланы (подушка)",
        "Пенсионный план",
        "Инвестиции в бизнес"
    ]
}

CURRENCIES = ["RUB", "USD", "EUR", "KZT"]
CARDS = ["Тинькофф", "Альфа", "Сбер", "Freedom"]

# === Инициализация бота ===
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# === Состояния FSM ===
class TransactionForm(StatesGroup):
    waiting_for_action = State()
    category = State()
    subcategory = State()
    amount = State()
    currency = State()
    date = State()
    card = State()
    comment = State()
    final_confirmation = State()

# === КЛАВИАТУРЫ ===
def main_menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Новая транзакция")
    kb.add("📋 Мои транзакции")
    kb.add("📊 Статистика")
    kb.add("⚙️ Настройки")
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
    if subs:
        for sub in subs:
            kb.add(sub)
    else:
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

# === ПРЕВЬЮ ТРАНЗАКЦИИ ===
def build_preview(data: dict) -> str:
    currency = data.get('currency', 'RUB')
    amount = data.get('amount', 0)
    rate = data.get('rate', 1.0)
    amount_rub = data.get('amount_rub', amount)

    currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}
    symbol = currency_symbols.get(currency, currency)

    preview = (
        f"📝 <b>Предварительный просмотр:</b>\n\n"
        f"📅 Дата: <code>{data.get('date', '')}</code>\n"
        f"📂 Категория: <code>{data.get('category', '')}</code>\n"
    )
    if data.get('subcategory'):
        preview += f"📁 Подкатегория: <code>{data['subcategory']}</code>\n"

    if currency == "RUB":
        preview += f"💰 Сумма: <code>{float(amount):,.2f}</code> ₽\n"
    else:
        preview += (
            f"💰 Сумма: <code>{float(amount):,.2f}</code> {symbol}\n"
            f"💱 Курс ЦБ: <code>{float(rate):,.2f}</code> ₽/{symbol}\n"
            f"🔄 В рублях: <code>{float(amount_rub):,.2f}</code> ₽\n"
        )

    if data.get('card'):
        preview += f"💳 Карта: <code>{data['card']}</code>\n"
    if data.get('comment'):
        preview += f"🏪 Место: <code>{data['comment']}</code>\n"
    return preview

# === УВЕДОМЛЕНИЕ АДМИНУ ===
async def notify_admin(message_text: str, user: types.User = None):
    if not ADMIN_ID:
        return
    user_info = ""
    if user:
        username = f"@{user.username}" if user.username else ""
        full_name = user.full_name if user.full_name else ""
        user_id = user.id
        user_info = f"\n👤 Пользователь: {full_name} {username} (ID: {user_id})"
    full_message = f"🔔 <b>Новая транзакция</b>\n{message_text}{user_info}"
    try:
        await bot.send_message(ADMIN_ID, full_message, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ Не удалось отправить уведомление админу: {e}")

# === /start ===
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if ALLOWED_IDS and user_id not in ALLOWED_IDS:
        await message.answer("🔒 У вас нет доступа к этому боту.")
        return

    await state.finish()
    await TransactionForm.waiting_for_action.set()

    welcome = (
        "👋 <b>Добро пожаловать в Finance Bot!</b>\n\n"
        "Этот бот автоматически записывает ваши финансовые транзакции в Google Таблицу.\n\n"
        "📱 <b>Автоматический режим:</b>\n"
        "— Shortcut на iPhone → автоматическое предложение записать\n"
        "— PDF выписка → загрузи файл боту\n\n"
        "✍️ <b>Ручной режим:</b>\n"
        "— Нажмите «➕ Новая транзакция»\n\n"
        "Выберите действие:"
    )
    await message.answer(welcome, parse_mode="HTML", reply_markup=main_menu_kb())

# === ГЛАВНОЕ МЕНЮ ===
@dp.message_handler(lambda message: message.text == "➕ Новая транзакция", state="*")
async def new_transaction(message: types.Message, state: FSMContext):
    await state.finish()
    await TransactionForm.category.set()
    await message.answer("Выберите категорию:", reply_markup=categories_kb())

# === ВЫБОР КАТЕГОРИИ ===
@dp.message_handler(state=TransactionForm.category)
async def process_category(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.waiting_for_action.set()
        await message.answer("Выберите действие:", reply_markup=main_menu_kb())
        return

    if message.text not in CATEGORIES:
        await message.answer("Выберите категорию из списка:", reply_markup=categories_kb())
        return

    await state.update_data(category=message.text)

    if CATEGORIES[message.text]:
        await TransactionForm.subcategory.set()
        await message.answer(f"Выберите подкатегорию для '{message.text}':", reply_markup=subcategories_kb(message.text))
    else:
        await state.update_data(subcategory="")
        data = await state.get_data()
        if data.get('from_webhook'):
            await TransactionForm.final_confirmation.set()
            await message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())
        else:
            await TransactionForm.amount.set()
            await message.answer("Введите сумму:", reply_markup=back_kb())

# === ВЫБОР ПОДКАТЕГОРИИ ===
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
    if data.get('from_webhook'):
        await TransactionForm.final_confirmation.set()
        await message.answer(build_preview(data), parse_mode="HTML", reply_markup=confirmation_kb())
    else:
        await TransactionForm.amount.set()
        await message.answer("Введите сумму:", reply_markup=back_kb())

# === ВВОД СУММЫ ===
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

# === ВЫБОР ВАЛЮТЫ ===
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
    amount = data.get('amount', 0)

    rate = get_cbr_rate(currency)
    amount_rub = round(float(amount) * rate, 2)

    await state.update_data(currency=currency, rate=rate, amount_rub=amount_rub)

    await TransactionForm.date.set()
    today = datetime.now().strftime("%d.%m.%Y, %H:%M")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(today)
    kb.add("⏪ Назад")
    await message.answer("Введите дату и время или нажмите кнопку:", reply_markup=kb)

# === ВВОД ДАТЫ ===
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
        await message.answer(
            "Введите дату в формате ДД.ММ.ГГГГ, ЧЧ:ММ (например: 09.03.2026, 14:35):",
            reply_markup=back_kb()
        )
        return

    await state.update_data(date=date_str)
    await TransactionForm.card.set()
    await message.answer("Выберите карту/счёт или пропустите:", reply_markup=cards_kb())

# === ВЫБОР КАРТЫ ===
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

# === КОММЕНТАРИЙ ===
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

# === ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ ===
@dp.message_handler(state=TransactionForm.final_confirmation)
async def final_confirmation(message: types.Message, state: FSMContext):
    if message.text == "✅ Записать":
        data = await state.get_data()

        try:
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
            ]
            ws.append_row(new_row)

            await notify_admin(
                f"📊 Транзакция\n"
                f"Категория: {data.get('category', '')}\n"
                f"Сумма: {float(amount):,.2f} {currency}\n"
                f"В рублях: {float(amount_rub):,.2f} ₽",
                message.from_user
            )

            await message.answer("✅ Транзакция записана!", reply_markup=main_menu_kb())
            await state.finish()

        except Exception as e:
            logging.error(f"Ошибка записи в Google Sheets: {e}")
            await message.answer(f"❌ Ошибка при записи: {e}\nПопробуйте ещё раз.", reply_markup=main_menu_kb())
            await state.finish()

    elif message.text == "✏️ Изменить":
        await TransactionForm.category.set()
        await message.answer("Начнём заново. Выберите категорию:", reply_markup=categories_kb())

    elif message.text == "❌ Отменить":
        await state.finish()
        await message.answer("Операция отменена.", reply_markup=main_menu_kb())

# === ПРОСМОТР ТРАНЗАКЦИЙ ===
@dp.message_handler(lambda message: message.text == "📋 Мои транзакции", state="*")
async def my_transactions(message: types.Message):
    try:
        ws = sh.worksheet("Транзакции")
        records = ws.get_all_records()

        if not records:
            await message.answer("📂 Нет транзакций.", reply_markup=main_menu_kb())
            return

        last_10 = records[-10:]
        text = "📋 <b>Последние 10 транзакций:</b>\n\n"

        currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}

        for rec in last_10:
            currency = rec.get('Валюта', 'RUB')
            amount = rec.get('Сумма', 0)
            amount_rub = rec.get('Сумма в RUB', amount)
            symbol = currency_symbols.get(currency, currency)

            text += (
                f"📅 {rec.get('Дата', '')}\n"
                f"📂 {rec.get('Категория', '')} → {rec.get('Подкатегория', '')}\n"
                f"💰 {float(amount):,.0f} {symbol}"
            )
            if currency != 'RUB':
                text += f" ({float(amount_rub):,.0f} ₽)"
            text += (
                f"\n💳 {rec.get('Карта', '')}\n"
                f"{'─' * 30}\n"
            )

        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())

    except Exception as e:
        logging.error(f"Ошибка чтения транзакций: {e}")
        await message.answer("❌ Ошибка при загрузке транзакций.", reply_markup=main_menu_kb())

# === СТАТИСТИКА ===
@dp.message_handler(lambda message: message.text == "📊 Статистика", state="*")
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
            date_str = str(rec.get('Дата', ''))
            date_part = date_str.split(',')[0].strip()
            try:
                dt = datetime.strptime(date_part, "%d.%m.%Y")
                if dt.strftime("%m.%Y") == current_month:
                    cat = rec.get('Категория', 'Прочее')
                    amount_rub = float(rec.get('Сумма в RUB', rec.get('Сумма', 0)))
                    category_totals[cat] = category_totals.get(cat, 0) + amount_rub
            except ValueError:
                continue

        if not category_totals:
            await message.answer("📂 Нет транзакций за текущий месяц.", reply_markup=main_menu_kb())
            return

        total = sum(category_totals.values())
        text = f"📊 <b>Статистика за {current_month}:</b>\n\n"

        for cat, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            percent = (amount / total) * 100
            text += f"📂 {cat}: {amount:,.0f} ₽ ({percent:.1f}%)\n"

        text += f"\n{'═' * 30}\n"
        text += f"💰 <b>ИТОГО:</b> {total:,.0f} ₽"

        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())

    except Exception as e:
        logging.error(f"Ошибка расчёта статистики: {e}")
        await message.answer("❌ Ошибка при расчёте статистики.", reply_markup=main_menu_kb())

# === Settings ===
@dp.message_handler(lambda m: m.text == "⚙️ Настройки", state="*")
async def settings(message: types.Message):
    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n👤 Ваш ID: <code>{message.from_user.id}</code>\n"
        f"🗄 Google Sheets: {'✅ Подключён' if sh else '❌ Не подключён'}",
        parse_mode="HTML", reply_markup=main_menu_kb()
    )

# === Неизвестные сообщения ===
@dp.message_handler(state="*")
async def unknown_message(message: types.Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Не понимаю. Используйте меню 👇", reply_markup=main_menu_kb())

# === WEBHOOK ДЛЯ SHORTCUTS/n8n ===
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

        currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}
        symbol = currency_symbols.get(currency, currency)

        message_text = (
            f"🔔 <b>Новая транзакция:</b>\n\n"
            f"💰 Сумма: {amount:,.2f} {symbol}\n"
        )
        if currency != 'RUB':
            message_text += f"🔄 В рублях: {amount_rub:,.2f} ₽\n"
        message_text += (
            f"🏪 Место: {merchant}\n"
            f"💳 Карта: {card}\n"
            f"📅 Дата: {date}\n\n"
            f"Хотите записать эту транзакцию?"
        )

        tx_id = str(uuid.uuid4())[:8]
        pending_transactions[tx_id] = {
            "a": amount,
            "m": merchant,
            "c": card,
            "d": date,
            "cur": currency,
            "rate": rate,
            "a_rub": amount_rub
        }

        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"wb|{tx_id}"),
            types.InlineKeyboardButton("❌ Нет", callback_data="wb|no")
        )

        import requests as req
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        tg_response = req.post(tg_url, json={
            "chat_id": user_id,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": kb.to_python()
        })
        logging.info(f"Telegram response: {tg_response.status_code} {tg_response.text}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"Ошибка webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# === ОБРАБОТКА WEBHOOK КНОПОК ===
@dp.callback_query_handler(lambda c: c.data.startswith("wb|"))
async def process_webhook_callback(callback: types.CallbackQuery, state: FSMContext):
    payload = callback.data[3:]
    if payload == "no":
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("❌ Транзакция пропущена.")
        await callback.answer()
        return

    tx = pending_transactions.pop(payload, None)
    if not tx:
        await callback.message.edit_text("❌ Транзакция устарела.")
        return

    await state.update_data(
        amount=tx.get('a', 0),
        currency=tx.get('cur', 'RUB'),
        rate=tx.get('rate', 1.0),
        amount_rub=tx.get('a_rub', tx.get('a', 0)),
        card=tx.get('c', ''),
        date=tx.get('d', datetime.now().strftime('%d.%m.%Y, %H:%M')),
        comment=tx.get('m', ''),
        from_webhook=True
    )

    currency_symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}
    currency = tx.get('cur', 'RUB')
    symbol = currency_symbols.get(currency, currency)

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
    logging.info("🚀 Finance Bot запущен!")
    run_bot()
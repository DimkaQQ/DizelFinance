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
        "— SMS от банка → автоматическое предложение записать\n"
        "— Email от банка → автоматическое предложение записать\n\n"
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
    
    # Если есть подкатегории
    if CATEGORIES[message.text]:
        await TransactionForm.subcategory.set()
        await message.answer(f"Выберите подкатегорию для '{message.text}':", reply_markup=subcategories_kb(message.text))
    else:
        await state.update_data(subcategory="")
        await TransactionForm.amount.set()
        await message.answer("Введите сумму (₽):", reply_markup=back_kb())

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

    await TransactionForm.amount.set()
    await message.answer("Введите сумму (₽):", reply_markup=back_kb())

# === ВВОД СУММЫ ===
@dp.message_handler(state=TransactionForm.amount)
async def process_amount(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        data = await state.get_data()
        category = data.get("category")
        if CATEGORIES[category]:
            await TransactionForm.subcategory.set()
            await message.answer(f"Выберите подкатегорию:", reply_markup=subcategories_kb(category))
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
    await TransactionForm.date.set()
    
    today = datetime.now().strftime("%d.%m.%Y")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(today)
    kb.add("⏪ Назад")
    
    await message.answer(f"Введите дату (например: {today}) или нажмите кнопку:", reply_markup=kb)

# === ВВОД ДАТЫ ===
@dp.message_handler(state=TransactionForm.date)
async def process_date(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.amount.set()
        await message.answer("Введите сумму (₽):", reply_markup=back_kb())
        return

    # Проверка формата даты
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
    except ValueError:
        await message.answer("Введите дату в формате ДД.ММ.ГГГГ (например: 20.01.2025):", reply_markup=back_kb())
        return

    await state.update_data(date=message.text)
    await TransactionForm.card.set()
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Тинькофф", "Альфа", "Сбер")
    kb.add("Пропустить")
    kb.add("⏪ Назад")
    
    await message.answer("Выберите карту/счёт или пропустите:", reply_markup=kb)

# === ВЫБОР КАРТЫ ===
@dp.message_handler(state=TransactionForm.card)
async def process_card(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.date.set()
        today = datetime.now().strftime("%d.%m.%Y")
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(today)
        kb.add("⏪ Назад")
        await message.answer(f"Введите дату:", reply_markup=kb)
        return

    card = "" if message.text == "Пропустить" else message.text
    await state.update_data(card=card)
    await TransactionForm.comment.set()
    await message.answer("Добавьте комментарий (или пропустите):", reply_markup=skip_kb())

# === КОММЕНТАРИЙ ===
@dp.message_handler(state=TransactionForm.comment)
async def process_comment(message: types.Message, state: FSMContext):
    if message.text == "⏪ Назад":
        await TransactionForm.card.set()
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add("Тинькофф", "Альфа", "Сбер")
        kb.add("Пропустить")
        kb.add("⏪ Назад")
        await message.answer("Выберите карту/счёт:", reply_markup=kb)
        return

    comment = "" if message.text == "Пропустить" else message.text
    await state.update_data(comment=comment)
    
    # Показываем превью
    data = await state.get_data()
    preview = (
        f"📝 <b>Предварительный просмотр:</b>\n\n"
        f"📅 Дата: <code>{data['date']}</code>\n"
        f"📂 Категория: <code>{data['category']}</code>\n"
    )
    if data.get('subcategory'):
        preview += f"📁 Подкатегория: <code>{data['subcategory']}</code>\n"
    preview += (
        f"💰 Сумма: <code>{data['amount']:,.2f}</code> ₽\n"
    )
    if data.get('card'):
        preview += f"💳 Карта: <code>{data['card']}</code>\n"
    if comment:
        preview += f"💬 Комментарий: <code>{comment}</code>\n"

    await TransactionForm.final_confirmation.set()
    await message.answer(preview, parse_mode="HTML", reply_markup=confirmation_kb())

# === ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ ===
@dp.message_handler(state=TransactionForm.final_confirmation)
async def final_confirmation(message: types.Message, state: FSMContext):
    if message.text == "✅ Записать":
        data = await state.get_data()
        
        # Записываем в Google Sheets
        try:
            ws = sh.worksheet("Транзакции")
            new_row = [
                data['date'],
                data['category'],
                data.get('subcategory', ''),
                data['amount'],
                data.get('card', ''),
                data.get('comment', '')
            ]
            ws.append_row(new_row)
            
            await notify_admin(
                f"📊 Транзакция\n"
                f"Категория: {data['category']}\n"
                f"Сумма: {data['amount']:,.2f} ₽",
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
        
        # Показываем последние 10
        last_10 = records[-10:]
        text = "📋 <b>Последние 10 транзакций:</b>\n\n"
        
        for rec in last_10:
            text += (
                f"📅 {rec.get('Дата', '')}\n"
                f"📂 {rec.get('Категория', '')} → {rec.get('Подкатегория', '')}\n"
                f"💰 {rec.get('Сумма', 0):,.0f} ₽\n"
                f"💬 {rec.get('Комментарий', '')}\n"
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
        
        # Считаем расходы по категориям за текущий месяц
        current_month = datetime.now().strftime("%m.%Y")
        category_totals = {}
        
        for rec in records:
            date_str = rec.get('Дата', '')
            if date_str.endswith(current_month):
                cat = rec.get('Категория', 'Прочее')
                amount = float(rec.get('Сумма', 0))
                category_totals[cat] = category_totals.get(cat, 0) + amount
        
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

# === message error ===
@dp.message_handler(state="*")
async def unknown_message(message: types.Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Не понимаю. Используйте меню 👇", reply_markup=main_menu_kb())

# === WEBHOOK ДЛЯ SMS/EMAIL ===
app = Flask(__name__)

@app.route('/webhook/transaction', methods=['POST'])
def webhook_transaction():
    """
    Принимает данные от iPhone Shortcuts или Gmail парсера
    
    Формат JSON:
    {
        "amount": 5000.00,
        "merchant": "Пятёрочка",
        "card": "Тинькофф",
        "date": "20.01.2025",
        "user_id": 123456789
    }
    """
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id or (ALLOWED_IDS and int(user_id) not in ALLOWED_IDS):
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        # Отправляем уведомление пользователю
        message_text = (
            f"🔔 <b>Новая транзакция от банка:</b>\n\n"
            f"💰 Сумма: {data.get('amount', 0):,.2f} ₽\n"
            f"🏪 Место: {data.get('merchant', 'Неизвестно')}\n"
            f"💳 Карта: {data.get('card', 'Неизвестно')}\n"
            f"📅 Дата: {data.get('date', datetime.now().strftime('%d.%m.%Y'))}\n\n"
            f"Хотите записать эту транзакцию?"
        )
        
        cb = json.dumps({"a": data.get('amount'), "m": data.get('merchant',''), "c": data.get('card',''), "d": data.get('date','')}, ensure_ascii=False)
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"wb|{cb}"),
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
        await callback.message.edit_text("❌ Транзакция пропущена.")
        return
    
    tx = json.loads(payload)
    await state.update_data(
        amount=float(tx.get('a', 0)),
        card=tx.get('c', ''),
        date=tx.get('d', datetime.now().strftime('%d.%m.%Y')),
        comment=tx.get('m', '')
    )
    
    await callback.message.edit_text("Выберите категорию:")
    await TransactionForm.category.set()
    await callback.message.answer("Выберите категорию:", reply_markup=categories_kb())

# === ЗАПУСК БОТА ===
def run_bot():
    executor.start_polling(dp, skip_updates=True)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Запускаем Telegram бота
    logging.info("🚀 Finance Bot запущен!")
    run_bot()

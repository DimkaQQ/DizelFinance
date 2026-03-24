# -*- coding: utf-8 -*-
import os
import re
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

import requests
import gspread
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-now")

@app.template_filter("from_json")
def from_json_filter(value):
    try:
        return json.loads(value) if value else {}
    except Exception:
        return {}

APP_PASSWORD = os.getenv("WEB_APP_PASSWORD", "change-me-now")

SHEET_URL = os.getenv("SHEET_URL_LOGISTICS") or os.getenv("SHEET_URL")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(BASE_DIR, "finance-key.json")
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

logging.basicConfig(level=logging.INFO)

if not SHEET_URL:
    raise ValueError("Не задан SHEET_URL_LOGISTICS или SHEET_URL в .env")

if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError(f"Файл ключа Google не найден: {GOOGLE_SERVICE_ACCOUNT_FILE}")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    GOOGLE_SERVICE_ACCOUNT_FILE,
    scope
)
gc = gspread.authorize(creds)
sh = gc.open_by_url(SHEET_URL)

MACHINES = []
COMMON_ARTICLES = []

AUTO_FIELD_COL_MAP = {
    "ТО (плановое)": "E",
    "Ремонт (аварийный)": "G",
    "Налоги/штрафы": "L",
    "Парковка/база": "K",
    "Топливо (собственное)": "I",
    "Зарплата водителя": "H",
    "Резина/расходники": "D",
    "Кредит/лизинг": "N",
    "Прочие расходы": "F",
    "Выручка": "O",
    "Кол-во рейсов": "J",
    "Комментарий": "P"
}

AUTO_FIELDS = [
    "ТО (плановое)",
    "Ремонт (аварийный)",
    "Налоги/штрафы",
    "Кол-во рейсов",
    "Топливо (собственное)",
    "Зарплата водителя",
    "Резина/расходники",
    "Кредит/лизинг",
    "Прочие расходы",
    "Парковка/база"
]


def get_or_create_worksheet(title: str, rows: int = 1000, cols: int = 20):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def ensure_history_sheet():
    ws = get_or_create_worksheet("История", rows=3000, cols=10)
    first_row = ws.row_values(1)
    if not first_row:
        ws.append_row([
            "Дата",
            "Время",
            "Пользователь",
            "Раздел",
            "Данные_JSON",
            "Комментарий"
        ])
    return ws


def notify_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_CHAT_ID:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_ADMIN_CHAT_ID,
                "text": text
            },
            timeout=10
        )
    except Exception as e:
        logging.error(f"Ошибка отправки TG уведомления: {e}")


def log_history(section: str, data: dict, username: str):
    try:
        ws = ensure_history_sheet()
        now = datetime.now() + timedelta(hours=6)
        ws.append_row([
            now.strftime("%d/%m/%Y"),
            now.strftime("%H:%M:%S"),
            username,
            section,
            json.dumps(data, ensure_ascii=False),
            data.get("comment", "")
        ], value_input_option="USER_ENTERED")
    except Exception as e:
        logging.error(f"Ошибка записи в Историю: {e}")


def load_reference_data():
    global MACHINES, COMMON_ARTICLES
    try:
        ref = sh.worksheet("Справочники")
        MACHINES = [x for x in ref.col_values(1)[1:] if x]
        COMMON_ARTICLES = [x for x in ref.col_values(5)[1:] if x]
    except Exception as e:
        logging.error(f"Ошибка загрузки справочников: {e}")


def now_str():
    return (datetime.now() + timedelta(hours=6)).strftime("%d/%m/%Y")


def parse_debt_comment(comment):
    match = re.search(r'долг\s+"([^"]+)"', comment, re.IGNORECASE)
    return match.group(1).strip() if match else None


def format_tg_message(username: str, section: str, data: dict, result_text: str) -> str:
    return (
        f"🆕 Новая запись\n\n"
        f"👤 Пользователь: {username}\n"
        f"📂 Раздел: {section}\n"
        f"✅ Результат: {result_text}\n"
        f"📝 Данные: {json.dumps(data, ensure_ascii=False)}"
    )


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("menu"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if password == APP_PASSWORD and username:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("menu"))
        else:
            error = "Неверный пароль или не указано имя"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/menu")
@login_required
def menu():
    return render_template("menu.html", username=session.get("username"))


@app.route("/history")
@login_required
def history():
    try:
        ws = ensure_history_sheet()
        rows = ws.get_all_records()
        rows = list(reversed(rows))
    except Exception as e:
        logging.error(f"Ошибка чтения Истории: {e}")
        rows = []

    return render_template(
        "history.html",
        username=session.get("username"),
        rows=rows
    )


@app.route("/wizard/<section>")
@login_required
def wizard(section):
    load_reference_data()
    return render_template(
        "wizard.html",
        section=section,
        machines=MACHINES,
        auto_fields=AUTO_FIELDS,
        articles=COMMON_ARTICLES,
        username=session.get("username")
    )


@app.route("/api/wizard/save", methods=["POST"])
@login_required
def wizard_save():
    payload = request.get_json()
    section = payload.get("section")
    data = payload.get("data", {})
    username = session.get("username", "Веб")

    try:
        result = save_to_sheets(section, data)
        log_history(section, data, username)
        notify_telegram(format_tg_message(username, section, data, result))
        return jsonify({"ok": True, "message": result})
    except Exception as e:
        logging.error(f"Ошибка сохранения {section}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


def save_to_sheets(section, data):
    username = session.get("username", "Веб")
    date = now_str()

    if section == "auto":
        field = data.get("field", "")
        machine = data.get("machine", "")
        is_reis = field == "Кол-во рейсов"

        raw = str(data.get("value", "0")).replace(",", ".")
        value = int(float(raw)) if is_reis else float(raw)

        revenue_raw = str(data.get("revenue") or "0").replace(",", ".")
        revenue = float(revenue_raw)

        comment = data.get("comment", "")

        ws = sh.worksheet("Машины_месяц")
        new_row = len(ws.col_values(1)) + 1
        col = AUTO_FIELD_COL_MAP.get(field)

        if not col:
            raise ValueError(f"Неизвестное поле: {field}")

        ws.update_acell(f"A{new_row}", date)
        ws.update_acell(f"B{new_row}", username)
        ws.update_acell(f"C{new_row}", machine)
        ws.update_acell(f"{col}{new_row}", value)
        ws.update_acell(f"P{new_row}", comment)

        debt_msg = ""
        if is_reis and revenue:
            ws.update_acell(f"O{new_row}", revenue)
            debtor = parse_debt_comment(comment)

            if debtor:
                ws_d = sh.worksheet("Долги")
                dr = len(ws_d.col_values(1)) + 1
                ws_d.update_acell(f"A{dr}", date)
                ws_d.update_acell(f"B{dr}", username)
                ws_d.update_acell(f"C{dr}", machine)
                ws_d.update_acell(f"D{dr}", debtor)
                ws_d.update_acell(f"E{dr}", revenue)
                ws_d.update_acell(f"F{dr}", "ДОЛГ")
                ws_d.update_acell(f"G{dr}", comment)
                debt_msg = f" + долг на {debtor}"

        return f"Записано: {machine} / {field} = {value}{debt_msg}"

    elif section == "hire":
        ws = sh.worksheet("Найм")
        last_row = len(ws.col_values(1)) + 1

        ws.update_acell(f"A{last_row}", date)
        ws.update_acell(f"B{last_row}", username)
        ws.update_acell(f"C{last_row}", data.get("client", ""))
        ws.update_acell(f"D{last_row}", data.get("supplier", ""))
        ws.update_acell(f"E{last_row}", data.get("carrier", ""))
        ws.update_acell(f"F{last_row}", float(str(data.get("volume") or "0").replace(",", ".")))
        ws.update_acell(f"G{last_row}", float(str(data.get("client_sum") or "0").replace(",", ".")))
        ws.update_acell(f"H{last_row}", float(str(data.get("fuel_cost") or "0").replace(",", ".")))
        ws.update_acell(f"I{last_row}", float(str(data.get("carrier_cost") or "0").replace(",", ".")))
        ws.update_acell(f"O{last_row}", data.get("comment", ""))

        return f"Найм: {data.get('client')} → {data.get('carrier')}"

    elif section == "income":
        ws = sh.worksheet("Доходы")
        ws.append_row(
            [
                date,
                username,
                data.get("client", ""),
                float(str(data.get("amount") or "0").replace(",", ".")),
                data.get("comment", "")
            ],
            value_input_option="USER_ENTERED"
        )
        return f"Доход: {data.get('client')} — {data.get('amount')} ₽"

    elif section == "expenses":
        ws = sh.worksheet("Общие расходы")
        ws.append_row(
            [
                date,
                username,
                data.get("article", ""),
                float(str(data.get("amount") or "0").replace(",", ".")),
                data.get("comment", "")
            ],
            value_input_option="USER_ENTERED"
        )
        return f"Расход: {data.get('article')} — {data.get('amount')} ₽"

    elif section == "debt_payment":
        ws_d = sh.worksheet("Долги")
        dr = len(ws_d.col_values(1)) + 1

        ws_d.update_acell(f"A{dr}", date)
        ws_d.update_acell(f"B{dr}", username)
        ws_d.update_acell(f"C{dr}", "")
        ws_d.update_acell(f"D{dr}", data.get("debtor", ""))
        ws_d.update_acell(f"E{dr}", float(str(data.get("amount") or "0").replace(",", ".")))
        ws_d.update_acell(f"F{dr}", "ОПЛАТА")
        ws_d.update_acell(f"G{dr}", data.get("comment", ""))

        return f"Оплата {data.get('amount')} ₽ от {data.get('debtor')}"

    return "Записано"


@app.route("/api/debts")
@login_required
def api_debts():
    try:
        ws_debt = sh.worksheet("Долги")
        records = ws_debt.get_all_records()
        balances = {}

        for rec in records:
            name = str(rec.get("Должник", "")).strip()
            summa = rec.get("Сумма", 0)
            tip = str(rec.get("Тип", "")).strip().upper()

            if not name:
                continue

            try:
                summa = float(str(summa).replace(",", "."))
            except Exception:
                summa = 0.0

            balances[name] = balances.get(name, 0.0)

            if tip == "ДОЛГ":
                balances[name] += summa
            elif tip == "ОПЛАТА":
                balances[name] -= summa

        active = {k: round(v, 2) for k, v in balances.items() if v > 0.01}
        return jsonify(active)

    except Exception as e:
        logging.error(f"Ошибка загрузки долгов: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    load_reference_data()
    ensure_history_sheet()
    app.run(host="0.0.0.0", port=5001, debug=False)
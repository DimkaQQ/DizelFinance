# -*- coding: utf-8 -*-
"""
Gmail Parser для Finance Bot
Читает письма от банков и отправляет данные в Telegram бот через webhook
"""

import os
import re
import base64
import requests
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv
import time

load_dotenv()

# === НАСТРОЙКИ ===
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:5000/webhook/transaction")
USER_ID = os.getenv("ADMIN_TELEGRAM_ID")

# === БАНКИ И ПАТТЕРНЫ ===
BANK_PATTERNS = {
    "tinkoff": {
        "from": "notify@tinkoff.ru",
        "patterns": {
            "amount": r"(\d+[\s,]?\d*\.?\d*)\s*₽",
            "merchant": r"(?:Покупка|Оплата)\s+(.+?)(?:\s+на|\s+₽|\n)",
            "card": r"Карта\s+\*(\d{4})"
        }
    },
    "alfa": {
        "from": "alfa@alfabank.ru",
        "patterns": {
            "amount": r"(\d+[\s,]?\d*\.?\d*)\s*(?:RUB|₽)",
            "merchant": r"Покупка\s+(.+?)(?:\s+на|\n)",
            "card": r"\*(\d{4})"
        }
    },
    "sber": {
        "from": "sberbank@sberbank.ru",
        "patterns": {
            "amount": r"Сумма:\s*(\d+[\s,]?\d*\.?\d*)",
            "merchant": r"Где:\s*(.+?)(?:\n|$)",
            "card": r"Карта:\s*\*(\d{4})"
        }
    }
}

def get_gmail_service():
    """Подключение к Gmail API"""
    creds = None
    
    # Проверяем существующий токен
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Если токена нет или он истёк
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Сохраняем токен
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def parse_email_body(body, bank_name):
    """Парсит тело письма и извлекает данные о транзакции"""
    bank_config = BANK_PATTERNS.get(bank_name)
    if not bank_config:
        return None
    
    patterns = bank_config['patterns']
    
    # Извлекаем сумму
    amount_match = re.search(patterns['amount'], body)
    amount = None
    if amount_match:
        amount_str = amount_match.group(1).replace(' ', '').replace(',', '.')
        try:
            amount = float(amount_str)
        except ValueError:
            pass
    
    # Извлекаем место покупки
    merchant_match = re.search(patterns['merchant'], body)
    merchant = merchant_match.group(1).strip() if merchant_match else "Неизвестно"
    
    # Извлекаем последние 4 цифры карты
    card_match = re.search(patterns['card'], body)
    card_last4 = card_match.group(1) if card_match else ""
    
    # Определяем название банка
    card_name = {
        "tinkoff": "Тинькофф",
        "alfa": "Альфа",
        "sber": "Сбер"
    }.get(bank_name, "Неизвестно")
    
    if card_last4:
        card_name = f"{card_name} *{card_last4}"
    
    return {
        "amount": amount,
        "merchant": merchant,
        "card": card_name,
        "date": datetime.now().strftime("%d.%m.%Y")
    }

def get_message_body(service, msg_id):
    """Получает тело письма"""
    try:
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # Проверяем структуру письма
        payload = message.get('payload', {})
        
        # Если письмо multipart
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        
        # Если письмо простое
        elif 'body' in payload:
            data = payload['body'].get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
        
        return None
        
    except Exception as e:
        print(f"❌ Ошибка получения тела письма: {e}")
        return None

def send_to_webhook(transaction_data):
    """Отправляет данные в webhook бота"""
    try:
        transaction_data['user_id'] = USER_ID
        response = requests.post(WEBHOOK_URL, json=transaction_data, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Транзакция отправлена в бот: {transaction_data['amount']} ₽")
            return True
        else:
            print(f"❌ Ошибка отправки: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка webhook: {e}")
        return False

def check_new_emails():
    """Проверяет новые письма от банков"""
    service = get_gmail_service()
    
    print("🔍 Проверяю новые письма от банков...")
    
    for bank_name, config in BANK_PATTERNS.items():
        try:
            # Ищем непрочитанные письма от банка
            query = f'from:{config["from"]} is:unread'
            results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
            messages = results.get('messages', [])
            
            if not messages:
                print(f"📭 Нет новых писем от {bank_name}")
                continue
            
            print(f"📬 Найдено {len(messages)} писем от {bank_name}")
            
            for msg in messages:
                msg_id = msg['id']
                
                # Получаем тело письма
                body = get_message_body(service, msg_id)
                if not body:
                    continue
                
                # Парсим транзакцию
                transaction = parse_email_body(body, bank_name)
                
                if transaction and transaction['amount']:
                    # Отправляем в бот
                    if send_to_webhook(transaction):
                        # Помечаем письмо как прочитанное
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        print(f"✅ Письмо {msg_id} обработано и помечено прочитанным")
                
        except Exception as e:
            print(f"❌ Ошибка обработки {bank_name}: {e}")

def main():
    """Основной цикл проверки почты"""
    print("🚀 Gmail Parser запущен!")
    print(f"📧 Проверяю почту каждые 30 секунд...")
    
    while True:
        try:
            check_new_emails()
            time.sleep(30)  # Проверяем каждые 30 секунд
            
        except KeyboardInterrupt:
            print("\n👋 Остановка парсера...")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()

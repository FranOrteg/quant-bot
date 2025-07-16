# src/alert.py
import os
import smtplib
import requests
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# === EMAIL ALERT ===
def send_trade_email(action, price, quantity, strategy, symbol):
    msg = EmailMessage()
    msg["Subject"] = f"🔔 Trade ejecutado: {action}"
    msg["From"] = os.getenv("ALERT_EMAIL_FROM")
    msg["To"] = os.getenv("ALERT_EMAIL_TO")

    msg.set_content(f"""
Trade ejecutado
-------------------------
Acción: {action}
Cantidad: {quantity} BTC
Precio: {price:.2f}
Par: {symbol}
Estrategia: {strategy}
    """)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(msg["From"], os.getenv("ALERT_EMAIL_PASS"))
            smtp.send_message(msg)
        print("📤 Alerta EMAIL enviada")
    except Exception as e:
        print(f"❌ Error al enviar EMAIL: {e}")

# === TELEGRAM ALERT (versión simplificada) ===
def send_trade_telegram(action, price, quantity, strategy, symbol):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    text = (
        "📣 Trade ejecutado\n"
        f"Acción   : {action}\n"
        f"Cantidad : {quantity} BTC\n"
        f"Precio   : {price:.2f}\n"
        f"Par      : {symbol}\n"
        f"Estrategia: {strategy}"
    )

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text"   : text,    
    }

    try:
        res = requests.post(url, data=payload, timeout=10)
        if res.status_code == 200:
            print("📤 Alerta TELEGRAM enviada")
        else:
            print(f"❌ Telegram error: {res.text}")
    except Exception as e:
        print(f"❌ Error al enviar TELEGRAM: {e}")

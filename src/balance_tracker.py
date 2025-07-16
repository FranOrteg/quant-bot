# balance_tracker.py

import os
import json
from dotenv import load_dotenv
from src.utils import log_performance

from binance.client import Client

# Carga variables de entorno
load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
use_real_balance = os.getenv("USE_REAL_BALANCE", "False") == "True"

client = Client(api_key, api_secret)

BALANCE_FILE = 'logs/balance.json'
DEFAULT_BALANCE = {
    "USDT": 10000.0,
    "BTC": 0.0
}

def load_balance():
    if use_real_balance:
        try:
            usdc_balance = float(client.get_asset_balance(asset='USDC')["free"])
            btc_balance = float(client.get_asset_balance(asset='BTC')["free"])
            balance = {
                "USDT": usdc_balance,  # o cambia la clave a "USDC" si tu sistema lo espera así
                "BTC": btc_balance
            }
            print("✅ Balance real cargado desde Binance:", balance)
            save_balance(balance)
            return balance
        except Exception as e:
            print("❌ Error al obtener balance real:", e)
            print("⚠️ Se usará balance simulado.")
    
    # Balance simulado (modo testing / sin conexión Binance)
    if not os.path.exists(BALANCE_FILE):
        save_balance(DEFAULT_BALANCE)
    with open(BALANCE_FILE, 'r') as f:
        return json.load(f)

def save_balance(balance):
    with open(BALANCE_FILE, 'w') as f:
        json.dump(balance, f, indent=2)

def update_balance(action, quantity, price):
    balance = load_balance()
    if action == "BUY":
        cost = quantity * price
        if balance["USDT"] >= cost:
            balance["USDT"] -= cost
            balance["BTC"] += quantity
    elif action == "SELL":
        if balance["BTC"] >= quantity:
            balance["BTC"] -= quantity
            balance["USDT"] += quantity * price
    save_balance(balance)
    log_performance(action, price, balance)

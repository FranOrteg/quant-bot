# balance_tracker.py

import os
import json
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_performance

load_dotenv()

BALANCE_FILE = 'logs/balance.json'
DEFAULT_BALANCE = {
    "USDC": 10000.0,
    "BTC": 0.0
}

USE_REAL_BALANCE = os.getenv("USE_REAL_BALANCE", "False") == "True"
print(f"🔍 USE_REAL_BALANCE: {USE_REAL_BALANCE}")

def fetch_binance_balance():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    client = Client(api_key, api_secret)
    account_info = client.get_account()
    usdc = btc = 0.0
    for asset in account_info['balances']:
        if asset['asset'] == 'USDC':
            usdc = float(asset['free'])  # Asumimos operativa con USDC
        elif asset['asset'] == 'BTC':
            btc = float(asset['free'])
    return {"USDC": usdc, "BTC": btc}

def load_balance():
    if USE_REAL_BALANCE:
        balance = fetch_binance_balance()
        save_balance(balance)
        print(f"✅ Balance real cargado desde Binance: {balance}")
        return balance
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
        if balance["USDC"] >= cost:
            balance["USDC"] -= cost
            balance["BTC"] += quantity
    elif action == "SELL":
        if balance["BTC"] >= quantity:
            balance["BTC"] -= quantity
            balance["USDC"] += quantity * price
    save_balance(balance)
    log_performance(action, price, balance)
    print_balance(balance)
    
def print_balance(balance):
    print(f"💰 Balance actual: {balance}")


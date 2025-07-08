# src/balance_tracker_5m.py
import os
import json
from src.utils import log_performance

BALANCE_FILE = 'logs/balance_5m.json'
DEFAULT_BALANCE = {
    "USDT": 10000.0,
    "BTC": 0.0
}

def load_balance():
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
    log_performance(action, price, balance, filename="logs/performance_log_5m.csv")

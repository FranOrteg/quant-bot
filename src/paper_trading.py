# src/paper_trading.py
import os
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime, timezone
import pandas as pd
import json

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret, testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'

quantity = 0.001  # ajusta según balance simulado

def get_price(symbol="BTCUSDT"):
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def buy(symbol, price, strategy_name, params):
    order = client.create_order(
        symbol=symbol,
        side='BUY',
        type='MARKET',
        quantity=quantity
    )
    print(f"✅ ORDEN COMPRA: {order}")
    log_trade(symbol, "BUY", price, strategy_name, params)
    return order

def sell(symbol, price, strategy_name, params):
    order = client.create_order(
        symbol=symbol,
        side='SELL',
        type='MARKET',
        quantity=quantity
    )
    print(f"✅ ORDEN VENTA: {order}")
    log_trade(symbol, "SELL", price, strategy_name, params)
    return order

def log_trade(symbol, action, price, strategy_name, params, filename='logs/trades.csv'):
    os.makedirs('logs', exist_ok=True)
    file_exists = os.path.isfile(filename)
    trade = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "strategy_name": strategy_name,
        "params": json.dumps(params)
    }
    pd.DataFrame([trade]).to_csv(filename, mode='a', index=False, header=not file_exists)

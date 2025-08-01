# src/paper_trading_5m.py

import os
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation
from src.balance_tracker_5m import update_balance
from src.alert import send_trade_email, send_trade_telegram

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

try:
    client = Client(api_key, api_secret, testnet=True)
    client.API_URL = 'https://testnet.binance.vision/api'
    client.ping()
except Exception as e:
    print(f"❌ Binance API error al iniciar: {e}")
    client = None

quantity = 0.001
FEE_RATE = 0.001
SLIPPAGE = 0.0005
symbol = os.getenv("TRADING_SYMBOL", "BTCUSDC")

def get_price(symbol=symbol):
    if client is None:
        print("⛔ No se puede obtener precio: Binance no disponible")
        return 0.0
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def buy(symbol, price, strategy_name, params, trades_path, perf_path):
    if client is None:
        print("⛔ No se puede ejecutar COMPRA: Binance no disponible")
        return None

    slippage_price = price * (1 + SLIPPAGE)
    fee = slippage_price * quantity * FEE_RATE

    print(f"🟢 COMPRANDO a {slippage_price:.2f} (+slippage), fee: {fee:.4f} USDC")

    log_operation(symbol, "BUY", slippage_price, strategy_name, params, trades_path)
    update_balance("BUY", quantity, slippage_price + fee)
    send_trade_email("BUY", slippage_price, quantity, strategy_name, symbol)
    send_trade_telegram("BUY", slippage_price, quantity, strategy_name, symbol)

    with open(perf_path, "a") as f:
        f.write(f"{pd.Timestamp.utcnow().isoformat()},BUY,{slippage_price},{quantity},{slippage_price * quantity},SUCCESS\n")

    return {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "executedQty": quantity,
        "price": slippage_price
    }

def sell(symbol, price, strategy_name, params, trades_path, perf_path):
    if client is None:
        print("⛔ No se puede ejecutar VENTA: Binance no disponible")
        return None

    slippage_price = price * (1 - SLIPPAGE)
    fee = slippage_price * quantity * FEE_RATE

    print(f"🔴 VENDIENDO a {slippage_price:.2f} (-slippage), fee: {fee:.4f} USDC")

    log_operation(symbol, "SELL", slippage_price, strategy_name, params, trades_path)
    update_balance("SELL", quantity, slippage_price - fee)
    send_trade_email("SELL", slippage_price, quantity, strategy_name, symbol)
    send_trade_telegram("SELL", slippage_price, quantity, strategy_name, symbol)

    with open(perf_path, "a") as f:
        f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL,{slippage_price},{quantity},{slippage_price * quantity},SUCCESS\n")

    return {
        "symbol": symbol,
        "side": "SELL",
        "type": "MARKET",
        "executedQty": quantity,
        "price": slippage_price
    }

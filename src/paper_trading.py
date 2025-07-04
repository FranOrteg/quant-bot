# src/paper_trading.py

import os
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation
from src.balance_tracker import update_balance

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

quantity = 0.001  # ajusta según tu balance simulado

FEE_RATE = 0.001      # 0.1%
SLIPPAGE = 0.0005     # 0.05%
STOP_LOSS = -0.005    # –0.5 %
TAKE_PROFIT =  0.01   # +1 %

def get_price(symbol="BTCUSDT"):
    if client is None:
        print("⛔ No se puede obtener precio: Binance no disponible")
        return 0.0
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def buy(symbol, price, strategy_name, params):
    if client is None:
        print("⛔ No se puede ejecutar COMPRA: Binance no disponible")
        return None

    slippage_price = price * (1 + SLIPPAGE)
    fee = slippage_price * quantity * FEE_RATE
    total_cost = slippage_price * quantity + fee

    print(f"🟢 COMPRANDO a {slippage_price:.2f} (+slippage), fee: {fee:.4f} USDT")

    order = {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "executedQty": quantity,
        "price": slippage_price
    }

    log_operation(symbol, "BUY", slippage_price, strategy_name, params)
    update_balance("BUY", quantity, slippage_price + (slippage_price * FEE_RATE))
    return order

def sell(symbol, price, strategy_name, params):
    if client is None:
        print("⛔ No se puede ejecutar VENTA: Binance no disponible")
        return None

    slippage_price = price * (1 - SLIPPAGE)
    fee = slippage_price * quantity * FEE_RATE
    total_gain = slippage_price * quantity - fee

    print(f"🔴 VENDIENDO a {slippage_price:.2f} (-slippage), fee: {fee:.4f} USDT")

    order = {
        "symbol": symbol,
        "side": "SELL",
        "type": "MARKET",
        "executedQty": quantity,
        "price": slippage_price
    }

    log_operation(symbol, "SELL", slippage_price, strategy_name, params)
    update_balance("SELL", quantity, slippage_price - (slippage_price * FEE_RATE))
    return order

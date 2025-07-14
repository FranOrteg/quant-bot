# src/paper_trading.py

import os
import inspect
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation
from src.balance_tracker import update_balance

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

try:
    # Si quieres usar el testnet, descomenta las siguientes dos líneas:
    # client = Client(api_key, api_secret, testnet=True)
    # client.API_URL = 'https://testnet.binance.vision/api'
    client = Client(api_key, api_secret)
    client.ping()
except Exception as e:
    print(f"❌ Binance API error al iniciar: {e}")
    client = None

quantity = 0.0002
FEE_RATE = 0.001
SLIPPAGE = 0.0005

# === NUEVO: detectar sufijo de script (ej. "5m" si se ejecuta desde live_trader_5m.py) ===
caller_file = os.path.basename(inspect.stack()[-1].filename)
suffix = "_5m" if "5m" in caller_file else "_15m"

# === rutas diferenciadas ===
trades_path = f"logs/trades{suffix}.csv"
perf_path   = f"logs/performance_log{suffix}.csv"

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

    print(f"🟢 COMPRANDO a {slippage_price:.2f} (+slippage), fee: {fee:.4f} USDT")

    log_operation(symbol, "BUY", slippage_price, strategy_name, params, trades_path)
    update_balance("BUY", quantity, slippage_price + (slippage_price * FEE_RATE), perf_path)

    return {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "executedQty": quantity,
        "price": slippage_price
    }

def sell(symbol, price, strategy_name, params):
    if client is None:
        print("⛔ No se puede ejecutar VENTA: Binance no disponible")
        return None

    slippage_price = price * (1 - SLIPPAGE)
    fee = slippage_price * quantity * FEE_RATE

    print(f"🔴 VENDIENDO a {slippage_price:.2f} (-slippage), fee: {fee:.4f} USDT")

    log_operation(symbol, "SELL", slippage_price, strategy_name, params, trades_path)
    update_balance("SELL", quantity, slippage_price - (slippage_price * FEE_RATE), perf_path)

    return {
        "symbol": symbol,
        "side": "SELL",
        "type": "MARKET",
        "executedQty": quantity,
        "price": slippage_price
    }

# src/real_trading.py

import os
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation
from src.balance_tracker import update_balance
from src.alert import send_trade_email, send_trade_telegram

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
client = Client(api_key, api_secret)

quantity = 0.0002  # ajusta si es necesario
symbol = os.getenv("TRADING_SYMBOL", "BTCUSDC")
FEE_RATE = 0.001

# rutas para logs (se heredan del sufijo del símbolo)
suffix = "_5m" if "5m" in os.getenv("TIMEFRAME", "15m") else "_15m"
trades_path = f"logs/trades{suffix}.csv"
perf_path   = f"logs/performance_log{suffix}.csv"

def buy(symbol, price, strategy_name, params):
    try:
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        fill = order["fills"][0]
        real_price = float(fill["price"])
        fee = real_price * quantity * FEE_RATE

        print(f"🟢 ORDEN REAL DE COMPRA ejecutada a {real_price:.2f} USDC (fee aprox: {fee:.4f})")

        log_operation(symbol, "BUY", real_price, strategy_name, params, trades_path)
        update_balance("BUY", quantity, real_price + fee)
        send_trade_email("BUY", real_price, quantity, strategy_name, symbol)
        send_trade_telegram("BUY", real_price, quantity, strategy_name, symbol)

        return order
    except Exception as e:
        print(f"❌ Error al ejecutar compra real: {e}")
        return None

def sell(symbol, price, strategy_name, params):
    try:
        order = client.order_market_sell(symbol=symbol, quantity=quantity)
        fill = order["fills"][0]
        real_price = float(fill["price"])
        fee = real_price * quantity * FEE_RATE

        print(f"🔴 ORDEN REAL DE VENTA ejecutada a {real_price:.2f} USDC (fee aprox: {fee:.4f})")

        log_operation(symbol, "SELL", real_price, strategy_name, params, trades_path)
        update_balance("SELL", quantity, real_price - fee)
        send_trade_email("SELL", real_price, quantity, strategy_name, symbol)
        send_trade_telegram("SELL", real_price, quantity, strategy_name, symbol)

        return order
    except Exception as e:
        print(f"❌ Error al ejecutar venta real: {e}")
        return None

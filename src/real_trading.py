# src/real_trading.py

import os
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation
from src.balance_tracker import update_balance
from src.alert import send_trade_email, send_trade_telegram
import pandas as pd

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
client = Client(api_key, api_secret)

quantity = 0.0002  # ajusta si es necesario
symbol = os.getenv("TRADING_SYMBOL", "BTCUSDC")
FEE_RATE = 0.001

def buy(symbol, price, strategy_name, params, trades_path, perf_path):
    try:
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        fill = order["fills"][0]
        real_price = float(fill["price"])
        fee = real_price * quantity * FEE_RATE
        
        with open(perf_path, "a") as f:
            f.write(f"{pd.Timestamp.utcnow().isoformat()},BUY,{real_price},{quantity},{real_price * quantity},SUCCESS\n")

        print(f"🟢 ORDEN REAL DE COMPRA ejecutada a {real_price:.2f} USDC (fee aprox: {fee:.4f})")

        log_operation(symbol, "BUY", real_price, strategy_name, params, trades_path)
        update_balance("BUY", quantity, real_price + fee)
        send_trade_email("BUY", real_price, quantity, strategy_name, symbol)
        send_trade_telegram("BUY", real_price, quantity, strategy_name, symbol)

        return order
    except Exception as e:
        print(f"❌ Error al ejecutar compra real: {e}")
        return None

def sell(symbol, price, strategy_name, params, trades_path, perf_path):
    try:
        # ✅ Comprobar balance real disponible
        balance_info = client.get_asset_balance(asset="BTC")
        free_btc = float(balance_info["free"])

        # ⚠️ Binance no permite órdenes menores a ~0.0001 BTC
        quantity_to_sell = round(free_btc, 6)

        if quantity_to_sell < 0.0001:
            print(f"❌ Saldo insuficiente para vender: tienes {free_btc} BTC")
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL_FAILED,{price},{free_btc},0,ERROR_INSUFFICIENT_BALANCE\n")
            return None

        # ✅ Ejecutar orden
        order = client.order_market_sell(symbol=symbol, quantity=quantity_to_sell)
        fill = order["fills"][0]
        real_price = float(fill["price"])
        fee = real_price * quantity_to_sell * FEE_RATE

        print(f"🔴 ORDEN REAL DE VENTA ejecutada a {real_price:.2f} USDC (qty: {quantity_to_sell}, fee aprox: {fee:.4f})")

        log_operation(symbol, "SELL", real_price, strategy_name, params, trades_path)
        update_balance("SELL", quantity_to_sell, real_price - fee)
        send_trade_email("SELL", real_price, quantity_to_sell, strategy_name, symbol)
        send_trade_telegram("SELL", real_price, quantity_to_sell, strategy_name, symbol)

        return order

    except Exception as e:
        print(f"❌ Error al ejecutar venta real: {e}")
        with open(perf_path, "a") as f:
            f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL_FAILED,{price},-,0,{str(e).replace(',', '')}\n")
        return None

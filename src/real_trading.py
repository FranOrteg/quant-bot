import os
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation, get_sellable_quantity
from src.balance_tracker import update_balance
from src.alert import send_trade_email, send_trade_telegram
from decimal import Decimal
import pandas as pd

load_dotenv()

api_key    = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
client     = Client(api_key, api_secret)

quantity   = 0.0002  # cantidad de prueba
symbol     = os.getenv("TRADING_SYMBOL", "BTCUSDC")
FEE_RATE   = 0.001

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
        qty_decimal = get_sellable_quantity(symbol, client)

        if qty_decimal == Decimal("0.0"):
            free_btc = client.get_asset_balance(asset="BTC")["free"]
            print(f"❌ Saldo ({free_btc} BTC) menor que minQty permitido")
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL_SKIPPED,{price},{free_btc},0,BELOW_MIN_QTY\n")
            return None
        
        qty_str = format(qty_decimal, ".6f")
        print(f"🔴 Ejecutando venta de {qty_str} BTC…")
        
        order = client.order_market_sell(symbol=symbol, quantity=qty_str)


        fill = order["fills"][0]
        real_price = float(fill["price"])
        fee = real_price * float(qty_decimal) * FEE_RATE

        log_operation(symbol, "SELL", real_price, strategy_name, params, trades_path)
        update_balance("SELL", float(qty_decimal), real_price - fee)
        send_trade_email("SELL", real_price, float(qty_decimal), strategy_name, symbol)
        send_trade_telegram("SELL", real_price, float(qty_decimal), strategy_name, symbol)

        with open(perf_path, "a") as f:
            f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL,{real_price},{float(qty_decimal)},{real_price*float(qty_decimal)},SUCCESS\n")

        print(f"✅ Venta ejecutada a {real_price:.2f} USDC")
        return order

    except Exception as e:
        print(f"❌ Error al vender: {e}")
        with open(perf_path, "a") as f:
            f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL_FAILED,{price},-,0,{str(e).replace(',', '')}\n")
        return None

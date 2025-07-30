# test_sell.py

import os
from binance.client import Client
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN

load_dotenv()

client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))

balance_info = client.get_asset_balance(asset="BTC")
free_btc = float(balance_info["free"])

print(f"BTC libre en cuenta: {free_btc:.8f}")

safety_margin = 0.995
qty_with_margin = free_btc * safety_margin

quantity_to_sell = float(
    Decimal(qty_with_margin).quantize(Decimal('0.000001'), rounding=ROUND_DOWN)
)

print(f"Cantidad con margen para venta: {quantity_to_sell:.6f}")

confirm = input("Confirmar orden de venta REAL ahora (sí/no): ")

if confirm.lower() == "sí":
    try:
        order = client.order_market_sell(symbol="BTCUSDC", quantity=quantity_to_sell)
        print("✅ Orden ejecutada correctamente:", order)
    except Exception as e:
        print("❌ Error ejecutando la orden:", e)
else:
    print("Operación cancelada por seguridad.")

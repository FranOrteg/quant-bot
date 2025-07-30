# test_sell.py

import os
from binance.client import Client
from dotenv import load_dotenv
from src.utils import get_sellable_quantity, format_quantity_for_binance
from decimal import Decimal

load_dotenv()

client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))

# 1. Calcular cantidad vendible
qty_to_sell_decimal = get_sellable_quantity("BTCUSDC", client)

if qty_to_sell_decimal == Decimal("0.0"):
    print("❌ No hay cantidad suficiente para vender.")
else:
    # 2. Formatear la cantidad para Binance
    symbol_info = client.get_symbol_info("BTCUSDC")
    lot_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size = Decimal(lot_filter["stepSize"])
    
    qty_str = format_quantity_for_binance(qty_to_sell_decimal, step_size)

    print(f"Cantidad a vender: {qty_str} BTC")
    confirm = input("Confirmar orden de venta REAL ahora (sí/no): ")

    if confirm.lower() == "sí":
        try:
            order = client.order_market_sell(symbol="BTCUSDC", quantity=qty_str)
            print("✅ Orden ejecutada correctamente:", order)
        except Exception as e:
            print("❌ Error ejecutando la orden:", e)
    else:
        print("Operación cancelada por seguridad.")

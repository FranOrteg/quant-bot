# scripts/manual_test.py

from src.paper_trading import buy, sell, get_price

symbol = "BTCUSDT"
strategy_name = "rsi_sma"
params = {"rsi_period": 14, "sma_period": 10, "rsi_buy": 40, "rsi_sell": 60}

# Obtener precio actual simulado
price = get_price(symbol)

# Simula COMPRA
print("\n--- SIMULANDO COMPRA ---")
buy(symbol, price, strategy_name, params)

# Simula VENTA
print("\n--- SIMULANDO VENTA ---")
sell(symbol, price * 1.01, strategy_name, params)  # asume 1% subida

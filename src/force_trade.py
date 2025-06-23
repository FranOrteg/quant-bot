from src.utils import log_operation

symbol = "BTCUSDT"
price = 105500.0  # puedes modificarlo
strategy_name = "rsi_sma"
params = {"rsi_period": 14, "sma_period": 10, "rsi_buy": 30, "rsi_sell": 70}

log_operation(symbol, "BUY", price, strategy_name, params)
print("✅ Señal forzada insertada en trades.csv")

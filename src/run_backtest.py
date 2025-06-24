# src/run_backtest.py

import pandas as pd
from src.backtest import backtest_signals
import matplotlib.pyplot as plt
import os
from src.report import generate_pdf_report
from src.binance_api import get_historical_data
from dotenv import load_dotenv
load_dotenv()

# === Cargar datos desde Binance API y guardarlos en CSV ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=60*24)
df.to_csv('data/BTCUSDT.csv', index=False)

# === Cargar estrategia desde .env ===
strategy_name = os.getenv('STRATEGY', 'rsi_sma')

if strategy_name == 'rsi_sma':
    from src.strategy.rsi_sma import rsi_sma_strategy as strategy
elif strategy_name == 'moving_average':
    from src.strategy import moving_average_crossover as strategy
elif strategy_name == 'macd':
    from src.strategy.macd import macd_strategy as strategy
else:
    raise ValueError(f"❌ Estrategia desconocida: {strategy_name}")

# === Aplicar estrategia ===
if strategy_name == 'moving_average':
    df = strategy(df, short_window=30, long_window=50)
else:
    df = strategy(df)


print(f"📌 Estrategia seleccionada: {strategy_name}\n")
print("🔎 Conteo de señales:")
print(df['position'].value_counts(), "\n")

columns_to_print = ['timestamp', 'close', 'position']
if strategy_name == 'rsi_sma':
    columns_to_print += ['RSI', 'SMA']
elif strategy_name == 'moving_average':
    columns_to_print += ['SMA20', 'SMA50']
elif strategy_name == 'macd':
    columns_to_print += ['MACD', 'Signal']

print(df[columns_to_print].tail(10))

# === Lanzar backtest ===
df, final_capital, metrics = backtest_signals(df)

# === Mostrar métricas ===
print("\n📊 Resultados del backtest:\n")
print(f"Capital final: ${final_capital:,.2f}")
print(f"Retorno total: {metrics['total_return']*100:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Máximo Drawdown: {metrics['max_drawdown']*100:.2f}%")

# === Gráfico ===
plt.plot(df['timestamp'], df['equity'])
plt.title("Evolución del capital")
plt.xlabel("Fecha")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("results/equity_curve.png")
print("\n📈 Gráfico guardado en results/equity_curve.png")

# === PDF con resultados ===
generate_pdf_report(strategy_name, metrics)

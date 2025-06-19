# src/analyze_trades.py

import pandas as pd
import matplotlib.pyplot as plt
import os

TRADES_PATH = 'logs/trades.csv'
PRICE_PATH = 'data/BTCUSDT.csv'
OUTPUT_PATH = 'results/trade_analysis.png'

# Leer datos
trades = pd.read_csv(TRADES_PATH)
prices = pd.read_csv(PRICE_PATH, names=['timestamp', 'close'], header=None)

# Parseo seguro de fechas
trades['timestamp'] = pd.to_datetime(trades['timestamp'], utc=True, errors='coerce')
prices['timestamp'] = pd.to_datetime(prices['timestamp'], utc=True, errors='coerce')

# 🔥 Eliminar filas con fechas inválidas
trades.dropna(subset=['timestamp'], inplace=True)
prices.dropna(subset=['timestamp'], inplace=True)

# Índices temporales
prices.set_index('timestamp', inplace=True)
trades = trades.set_index('timestamp').join(prices, how='left', rsuffix='_price')
trades.reset_index(inplace=True)

# Gráfico
plt.figure(figsize=(12, 6))
plt.plot(prices.index, prices['close'], label='BTCUSDT', color='blue', linewidth=1)

# Señales
buy_trades = trades[trades['action'] == 'BUY']
sell_trades = trades[trades['action'] == 'SELL']

plt.scatter(buy_trades['timestamp'], buy_trades['price'], color='green', marker='^', label='BUY', zorder=5)
plt.scatter(sell_trades['timestamp'], sell_trades['price'], color='red', marker='v', label='SELL', zorder=5)

# Estética
plt.title('Historial de operaciones BTCUSDT')
plt.xlabel('Fecha')
plt.ylabel('Precio (USD)')
plt.legend()
plt.grid(True)

# Guardado
os.makedirs('results', exist_ok=True)
plt.tight_layout()
plt.savefig(OUTPUT_PATH)
plt.close()

# Métricas
total_ops = len(trades)
buys = len(buy_trades)
sells = len(sell_trades)

if buys == sells:
    profit_ops = (sell_trades['price'].values - buy_trades['price'].values)
    total_profit = profit_ops.sum()
    profit_pct = (profit_ops / buy_trades['price'].values * 100).sum()
else:
    total_profit = '⚠️ BUY/SELL desbalanceado'
    profit_pct = '⚠️'

# Consola
print("\n📊 RESULTADOS:")
print(f"🔸 Total operaciones: {total_ops} ({buys} BUY, {sells} SELL)")
print(f"💵 Retorno acumulado: {total_profit} USD")
print(f"📈 Porcentaje acumulado: {profit_pct}%")
print(f"📸 Gráfico guardado en: {OUTPUT_PATH}")

# src/optimize_rsi.py

import pandas as pd
import matplotlib.pyplot as plt
from src.backtest import backtest_signals
from src.strategy.rsi_sma import rsi_sma_strategy
from src.binance_api import get_historical_data
import os
from datetime import datetime

# === Obtener datos reales ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)

# === Rango de parámetros a probar ===
rsi_periods = [5, 10, 14, 21]
sma_periods = [10, 15, 20, 30]
rsi_buy_levels = [40, 35, 30]
rsi_sell_levels = [60, 65, 70]

results = []

# === Pruebas cruzadas ===
for rsi_p in rsi_periods:
    for sma_p in sma_periods:
        for rsi_buy in rsi_buy_levels:
            for rsi_sell in rsi_sell_levels:
                if rsi_buy >= rsi_sell:
                    continue

                df_copy = df.copy()
                df_copy = rsi_sma_strategy(
                    df_copy,
                    period_rsi=rsi_p,
                    sma_period=sma_p,
                    rsi_buy=rsi_buy,
                    rsi_sell=rsi_sell
                )
                df_copy, capital, metrics = backtest_signals(df_copy)

                results.append({
                    'strategy': 'rsi_sma',
                    'rsi_period': rsi_p,
                    'sma_period': sma_p,
                    'rsi_buy': rsi_buy,
                    'rsi_sell': rsi_sell,
                    'capital_final': round(capital, 2),
                    'total_return': round(metrics['total_return'] * 100, 2),
                    'sharpe_ratio': round(metrics['sharpe_ratio'], 2),
                    'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
                    'timestamp': datetime.now().isoformat()
                })

# === Guardar resultados ===
os.makedirs('results', exist_ok=True)
results_df = pd.DataFrame(results)
results_df.to_csv('results/rsi_optimization.csv', index=False)

# === Mostrar top 5 setups ===
print("\n📈 Top 5 configuraciones RSI + SMA por retorno total:")
top5 = results_df.sort_values('total_return', ascending=False).head(5)
print(top5.to_string(index=False))

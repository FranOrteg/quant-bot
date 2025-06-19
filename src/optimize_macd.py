# src/optimize_macd.py

import pandas as pd
from src.backtest import backtest_signals
from src.strategy.macd import macd_strategy
from src.binance_api import get_historical_data
import os
from datetime import datetime

# === Obtener datos reales ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)

short_emas = [8, 12, 15]
long_emas = [20, 26, 30]
signal_emas = [5, 9, 12]

results = []

# === Pruebas cruzadas ===
for short in short_emas:
    for long in long_emas:
        if short >= long:
            continue
        for signal in signal_emas:
            df_copy = df.copy()
            df_copy = macd_strategy(
                df_copy,
                short_ema=short,
                long_ema=long,
                signal_ema=signal
            )
            df_copy, capital, metrics = backtest_signals(df_copy)

            results.append({
                'strategy': 'macd',
                'short_ema': short,
                'long_ema': long,
                'signal_ema': signal,
                'capital_final': round(capital, 2),
                'total_return': round(metrics['total_return'] * 100, 2),
                'sharpe_ratio': round(metrics['sharpe_ratio'], 2),
                'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
                'timestamp': datetime.now().isoformat()
            })

# === Guardar resultados ===
os.makedirs('results', exist_ok=True)
results_df = pd.DataFrame(results)
results_df.to_csv('results/macd_optimization.csv', index=False)

# === Mostrar top 5 setups ===
print("\n📈 Top 5 configuraciones MACD por retorno total:")
top5 = results_df.sort_values('total_return', ascending=False).head(5)
print(top5.to_string(index=False))

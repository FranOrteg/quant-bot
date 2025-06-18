import pandas as pd
from src.backtest import backtest_signals
from src.strategy import moving_average_crossover
from src.binance_api import get_historical_data
import os
from datetime import datetime

# === Obtener datos reales ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)

# === Combinaciones a probar ===
short_windows = [10, 15, 20, 30]
long_windows = [50, 75, 100, 120]

results = []

# === Probar todas las combinaciones ===
for short_w in short_windows:
    for long_w in long_windows:
        if short_w >= long_w:
            continue  # invalid: short must be < long

        df_copy = df.copy()
        df_copy = moving_average_crossover(df_copy, short_window=short_w, long_window=long_w)
        df_copy, capital, metrics = backtest_signals(df_copy)

        results.append({
            'strategy': 'moving_average',
            'short_window': short_w,
            'long_window': long_w,
            'capital_final': round(capital, 2),
            'total_return': round(metrics['total_return'] * 100, 2),
            'sharpe_ratio': round(metrics['sharpe_ratio'], 2),
            'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
            'timestamp': datetime.now().isoformat()
        })

# === Guardar resultados en CSV ===
os.makedirs('results', exist_ok=True)
results_df = pd.DataFrame(results)
results_df.to_csv('results/sma_optimization.csv', index=False)

# === Mostrar top 5 setups por retorno ===
print("\n📈 Top 5 combinaciones de SMA por Retorno Total:")
print("")
top5 = results_df.sort_values('total_return', ascending=False).head(5)
print(top5.to_string(index=False))

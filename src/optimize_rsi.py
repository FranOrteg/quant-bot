# src/optimize_rsi.py

import pandas as pd
import matplotlib.pyplot as plt
from src.backtest import backtest_signals
from src.strategy.rsi_sma import rsi_sma_strategy
from src.binance_api import get_historical_data
import os, argparse
from datetime import datetime

# ── CLI ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--timeframe", default="1h")
parser.add_argument("--limit",     type=int, default=8000)
parser.add_argument("--plot",      action="store_true", help="Generar gráfico del top 5")
args = parser.parse_args()

df = get_historical_data("BTC/USDT", args.timeframe, args.limit)

# === Rango de parámetros a probar ===
rsi_periods     = [5, 10, 14, 21]
sma_periods     = [10, 15, 20, 30]
rsi_buy_levels  = [40, 35, 30]
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
                    rsi_period=rsi_p,
                    sma_period=sma_p,
                    rsi_buy=rsi_buy,
                    rsi_sell=rsi_sell
                )
                df_copy, capital, metrics = backtest_signals(df_copy, timeframe=args.timeframe)

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
output = f"results/rsi_optimization_{args.timeframe}.csv"
results_df.to_csv(output, index=False)

# === Mostrar top 5 setups ===
print("\n📈 Top 5 configuraciones RSI + SMA por retorno total:")
top5 = results_df.sort_values('total_return', ascending=False).head(5)
print(top5.to_string(index=False))

# === Gráfico opcional ===
if args.plot:
    plt.figure(figsize=(10, 5))
    plt.bar(top5.index.astype(str), top5["total_return"], color='skyblue')
    plt.title(f"Top 5 RSI + SMA ({args.timeframe})")
    plt.ylabel("Retorno (%)")
    plt.xlabel("Setup")
    for i, row in top5.iterrows():
        label = f"{row['rsi_period']}/{row['sma_period']} | {row['rsi_buy']}-{row['rsi_sell']}"
        plt.text(i, row["total_return"] + 0.1, label, ha='center', fontsize=8, rotation=45)
    plt.tight_layout()
    plot_path = f"results/rsi_top5_{args.timeframe}.png"
    plt.savefig(plot_path)
    print(f"\n📊 Gráfico guardado en: {plot_path}")

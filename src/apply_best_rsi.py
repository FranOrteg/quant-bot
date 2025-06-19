# src/apply_best_rsi.py

import pandas as pd
from src.strategy.rsi_sma import rsi_sma_strategy
from src.binance_api import get_historical_data
from src.backtest import backtest_signals, generate_equity_plot, generate_pdf_report
import os

# === Leer la mejor configuración del CSV ===
csv_path = 'results/rsi_optimization.csv'
df_results = pd.read_csv(csv_path)
best_row = df_results.sort_values(by='total_return', ascending=False).iloc[0]

# === Extraer parámetros óptimos ===
rsi_period = int(best_row['rsi_period'])
sma_period = int(best_row['sma_period'])
rsi_buy = int(best_row['rsi_buy'])
rsi_sell = int(best_row['rsi_sell'])

print(f"\n✅ Ejecutando backtest con mejor configuración encontrada:")
print(f"Estrategia: rsi_sma, RSI{rsi_period}, SMA{sma_period}, Buy<{rsi_buy}, Sell>{rsi_sell}, Retorno: {best_row['total_return']}%\n")

# === Obtener datos y aplicar estrategia ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)
df = rsi_sma_strategy(df, period_rsi=rsi_period, sma_period=sma_period, rsi_buy=rsi_buy, rsi_sell=rsi_sell)

# === Ejecutar backtest y guardar resultados ===
df, capital_final, metrics = backtest_signals(df)

print(f"Capital final: ${capital_final:,.2f}")
print(f"Retorno total: {metrics['total_return']*100:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Máximo Drawdown: {metrics['max_drawdown']*100:.2f}%\n")

# === Guardar gráfico e informe ===
os.makedirs('results', exist_ok=True)
generate_equity_plot(df, filename='results/best_rsi_equity_curve.png')
generate_pdf_report(df, capital_final, metrics, strategy_name='RSI + SMA', filename='results/best_rsi_report.pdf')

print("📈 Gráfico guardado en results/best_rsi_equity_curve.png")
print("✅ Informe PDF generado en: results/best_rsi_report.pdf")

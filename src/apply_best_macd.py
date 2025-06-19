# src/apply_best_macd.py

import pandas as pd
from src.strategy.macd import macd_strategy
from src.binance_api import get_historical_data
from src.backtest import backtest_signals, generate_equity_plot
from src.report import generate_pdf_report

# === Cargar la mejor configuración desde CSV ===
df_best = pd.read_csv('results/macd_optimization.csv')
best_row = df_best.sort_values('total_return', ascending=False).iloc[0]

short_ema = int(best_row['short_ema'])
long_ema = int(best_row['long_ema'])
signal_ema = int(best_row['signal_ema'])

print(f"\n✅ Ejecutando backtest con mejor configuración encontrada:")
print(f"Estrategia: macd, EMA{short_ema}/{long_ema}, Señal: {signal_ema}, Retorno: {best_row['total_return']}%\n")

# === Obtener datos ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)

# === Aplicar estrategia y backtest ===
df = macd_strategy(df, short_ema, long_ema, signal_ema)
df, capital_final, metrics = backtest_signals(df)

# === Guardar gráfico ===
chart_path = 'results/best_macd_equity_curve.png'
generate_equity_plot(df, chart_path)

# === Generar informe PDF ===
generate_pdf_report(
    strategy_name=f"MACD EMA{short_ema}/{long_ema}, Señal {signal_ema}",
    metrics=metrics,
    chart_path=chart_path,
    output_path='results/best_macd_report.pdf'
)

# src/apply_best_strategy.py

import pandas as pd
import matplotlib.pyplot as plt
from src.backtest import backtest_signals
from src.strategy import moving_average_crossover
from src.binance_api import get_historical_data
from src.report import generate_pdf_report

# === Leer CSV de optimizaciones ===
data = pd.read_csv('results/sma_optimization.csv')

# === Seleccionar el mejor setup por retorno total ===
best = data.sort_values('total_return', ascending=False).iloc[0]
short_w = int(best['short_window'])
long_w = int(best['long_window'])

print(f"\n✅ Ejecutando backtest con mejor configuración encontrada:")
print(f"Estrategia: {best['strategy']}, SMA{short_w}/{long_w}, Retorno: {best['total_return']}%\n")

# === Obtener datos reales ===
df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)

# === Ejecutar estrategia con parámetros óptimos ===
df = moving_average_crossover(df, short_window=short_w, long_window=long_w)
df, capital, metrics = backtest_signals(df)

# === Mostrar resultados ===
print(f"Capital final: ${capital:,.2f}")
print(f"Retorno total: {metrics['total_return']*100:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Máximo Drawdown: {metrics['max_drawdown']*100:.2f}%")

# === Guardar gráfico ===
plt.plot(df['timestamp'], df['equity'])
plt.title("Mejor estrategia optimizada")
plt.xlabel("Fecha")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("results/best_equity_curve.png")
print("\n📈 Gráfico guardado en results/best_equity_curve.png")

# === Guardar informe PDF ===
generate_pdf_report("moving_average (opt)", metrics, chart_path="results/best_equity_curve.png", output_path="results/best_report.pdf")

import pandas as pd
from src.strategy import moving_average_crossover
from src.backtest import backtest_signals
import matplotlib.pyplot as plt

# Cargar datos reales
df = pd.read_csv('data/BTCUSDT.csv', parse_dates=['timestamp'])
df = df.sort_values('timestamp')

# Calcular señales con tu estrategia
df = moving_average_crossover(df)

print(df[['timestamp', 'close', 'SMA20', 'SMA50', 'position']].tail(10))

# Lanzar backtest
df, final_capital, metrics = backtest_signals(df)

# Mostrar métricas clave
print("📊 Resultados del backtest:")
print(f"Capital final: ${final_capital:,.2f}")
print(f"Retorno total: {metrics['total_return']*100:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Máximo Drawdown: {metrics['max_drawdown']*100:.2f}%")

# (Opcional) Gráfica de la equity curve
plt.plot(df['timestamp'], df['equity'])
plt.title("Evolución del capital")
plt.xlabel("Fecha")
plt.ylabel("Capital ($)")
plt.grid(True)
plt.tight_layout()
plt.savefig("results/equity_curve.png")
print("📈 Gráfico guardado en results/equity_curve.png")


import pandas as pd
from src.strategy.rsi_sma import rsi_sma_strategy
from src.backtest import backtest_signals
import matplotlib.pyplot as plt
import os
from dotenv import load_dotenv
load_dotenv()

# Cargar datos reales
df = pd.read_csv('data/BTCUSDT.csv', parse_dates=['timestamp'])
df = df.sort_values('timestamp')

# Calcular señales con tu estrategia
# df = moving_average_crossover(df)

# df = rsi_sma_strategy(df)

strategy_name = os.getenv('STRATEGY', 'rsi_sma')

if strategy_name == 'rsi_sma':
    from src.strategy.rsi_sma import rsi_sma_strategy as strategy
elif strategy_name == 'moving_average':
    from src.strategy import moving_average_crossover as strategy
else:
    raise ValueError(f"❌ Estrategia desconocida: {strategy_name}")

df = strategy(df)

print(f"📌 Estrategia seleccionada: {strategy_name}")
print("")

print("\n🔎 Conteo de señales:")
print(df['position'].value_counts())
print("")


columns_to_print = ['timestamp', 'close', 'position']


if strategy_name == 'rsi_sma':
    columns_to_print += ['RSI', 'SMA']
elif strategy_name == 'moving_average':
    columns_to_print += ['SMA20', 'SMA50']

print(df[columns_to_print].tail(10))

# Lanzar backtest
df, final_capital, metrics = backtest_signals(df)

# Mostrar métricas clave
print("📊 Resultados del backtest:")
print("")
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
print("")
print("📈 Gráfico guardado en results/equity_curve.png")


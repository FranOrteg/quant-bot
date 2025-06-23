# src/analyze_equity.py
import pandas as pd
import matplotlib.pyplot as plt
import os
import json

TRADES_PATH = "logs/trades.csv"
CHART_PATH = "results/trade_analysis.png"
METRICS_PATH = "results/trade_metrics.txt"

os.makedirs("results", exist_ok=True)

trades = pd.read_csv(TRADES_PATH)
trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True, errors='coerce')
trades = trades.dropna(subset=["timestamp", "price", "action"]).sort_values("timestamp")

initial_balance = 10000.0
btc_balance = 0.0
usdt_balance = initial_balance
equity_curve = []

for _, row in trades.iterrows():
    price = row["price"]
    if row["action"] == "BUY":
        btc_balance += 0.001
        usdt_balance -= 0.001 * price
    elif row["action"] == "SELL":
        btc_balance -= 0.001
        usdt_balance += 0.001 * price
    equity = usdt_balance + btc_balance * price
    equity_curve.append((row["timestamp"], equity))

df = pd.DataFrame(equity_curve, columns=["timestamp", "equity"])
df.to_csv("results/equity.csv", index=False)

# Métricas
final_equity = df["equity"].iloc[-1]
total_return = final_equity - initial_balance
return_pct = (total_return / initial_balance) * 100
drawdown = (df["equity"].cummax() - df["equity"]).max()

with open(METRICS_PATH, "w") as f:
    f.write(f"Operaciones: {len(trades)}\n")
    f.write(f"Equity final: {final_equity:.2f} USDT\n")
    f.write(f"Retorno total: {total_return:.2f} USDT\n")
    f.write(f"Retorno porcentaje: {return_pct:.2f}%\n")
    f.write(f"Drawdown máximo: {drawdown:.2f} USDT\n")

# Plot
plt.figure(figsize=(10, 5))
plt.plot(df["timestamp"], df["equity"], label="Equity", color="blue")
plt.title("📈 Evolución del Capital (Equity)")
plt.xlabel("Fecha")
plt.ylabel("Capital Total (USDT)")
plt.grid(True)
plt.tight_layout()
plt.savefig(CHART_PATH)

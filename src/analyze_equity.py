# src/analyze_equity.py

import pandas as pd
import matplotlib.pyplot as plt
import os
import json
import re

def generate_equity_chart(trades_path, chart_path, initial_balance=10_000.0):
    if not os.path.exists(trades_path):
        print(f"❌ No se encontró {trades_path}")
        return

    df = pd.read_csv(trades_path)

    df["timestamp"] = df["timestamp"].astype(str).apply(
        lambda s: re.sub(r"\.\d{1,6}\+00:00$", "+00:00", s)
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["timestamp", "price", "action"]).sort_values("timestamp")

    btc_balance = 0.0
    usdt_balance = initial_balance
    equity_curve = []

    for _, row in df.iterrows():
        price = row["price"]
        if row["action"].upper() == "BUY":
            btc_balance += 0.001
            usdt_balance -= 0.001 * price
        elif row["action"].upper() == "SELL":
            btc_balance -= 0.001
            usdt_balance += 0.001 * price

        equity = usdt_balance + btc_balance * price
        equity_curve.append((row["timestamp"], equity))

    eq_df = pd.DataFrame(equity_curve, columns=["timestamp", "equity"])
    os.makedirs(os.path.dirname(chart_path), exist_ok=True)
    eq_df.to_csv("results/equity.csv", index=False)

    # Gráfico
    plt.figure(figsize=(10, 5))
    plt.plot(eq_df["timestamp"], eq_df["equity"])
    plt.title("Evolución del Capital (Equity)")
    plt.xlabel("Fecha")
    plt.ylabel("Capital Total (USDT)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    print("✅ Gráfico de equity guardado en", chart_path)

# Ejecutar directamente como script si se desea
if __name__ == "__main__":
    generate_equity_chart("logs/trades.csv", "results/trade_analysis.png")

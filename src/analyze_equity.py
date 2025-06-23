# src/analyze_equity.py
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
import re

TRADES_PATH = "logs/trades.csv"
CHART_PATH  = "results/trade_analysis.png"
METRICS_PATH = "results/trade_metrics.txt"
INITIAL_BALANCE = 10_000.0

def main() -> None:
    if not os.path.exists(TRADES_PATH):
        print("❌  No se encontró logs/trades.csv")
        return

    # -------- leer & normalizar --------------------------------------
    df = pd.read_csv(TRADES_PATH)

    # quitar microsegundos (.xxxxxx) para compatibilidad pandas 1.x
    df["timestamp"] = df["timestamp"].astype(str).apply(
        lambda s: re.sub(r"\.\d{1,6}\+00:00$", "+00:00", s)
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["timestamp", "price", "action"]).sort_values("timestamp")

    # -------- recorrer trades y calcular equity ----------------------
    btc_balance   = 0.0
    usdt_balance  = INITIAL_BALANCE
    equity_curve  = []

    for _, row in df.iterrows():
        price = row["price"]
        if row["action"].upper() == "BUY":
            btc_balance  += 0.001
            usdt_balance -= 0.001 * price
        elif row["action"].upper() == "SELL":
            btc_balance  -= 0.001
            usdt_balance += 0.001 * price

        equity = usdt_balance + btc_balance * price
        equity_curve.append((row["timestamp"], equity))

    eq_df = pd.DataFrame(equity_curve, columns=["timestamp", "equity"])
    os.makedirs("results", exist_ok=True)
    eq_df.to_csv("results/equity.csv", index=False)

    # -------- métricas ----------------------------------------------
    final_equity  = eq_df["equity"].iloc[-1]
    total_return  = final_equity - INITIAL_BALANCE
    return_pct    = (total_return / INITIAL_BALANCE) * 100
    drawdown      = (eq_df["equity"].cummax() - eq_df["equity"]).max()

    with open(METRICS_PATH, "w") as f:
        f.write(f"Operaciones: {len(df)}\n")
        f.write(f"Equity final: {final_equity:.2f} USDT\n")
        f.write(f"Retorno total: {total_return:.2f} USDT\n")
        f.write(f"Retorno porcentaje: {return_pct:.2f}%\n")
        f.write(f"Drawdown máximo: {drawdown:.2f} USDT\n")

    # -------- gráfico -----------------------------------------------
    plt.figure(figsize=(10, 5))
    plt.plot(eq_df["timestamp"], eq_df["equity"])
    plt.title("Evolución del Capital (Equity)")
    plt.xlabel("Fecha")
    plt.ylabel("Capital Total (USDT)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(CHART_PATH)
    plt.close()

    print("✅  trade_metrics.txt y gráfico actualizados.")

if __name__ == "__main__":
    main()

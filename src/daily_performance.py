# src/daily_performance.py
import pandas as pd
import os
import re
from datetime import datetime, timezone

TRADES_PATH          = "logs/trades.csv"
PERFORMANCE_LOG_PATH = "logs/performance_log.csv"
INITIAL_BALANCE      = 10_000.0          # capital inicial

def calculate_daily_performance() -> None:
    if not os.path.exists(TRADES_PATH):
        print("❌  No se encontró logs/trades.csv")
        return

    # --- leer y limpiar ------------------------------------------------
    df = pd.read_csv(TRADES_PATH)

    # 1️⃣  normalizar → quitar microsegundos (.xxxxxx) para compat. pandas 1.x
    df["timestamp"] = df["timestamp"].astype(str).apply(
        lambda s: re.sub(r"\.\d{1,6}\+00:00$", "+00:00", s)
    )

    # 2️⃣  convertir a datetime UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    # 3️⃣  asegurar price numérico
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # 4️⃣  descartar filas inválidas y ordenar
    df = df.dropna(subset=["timestamp", "price", "action"]).sort_values("timestamp")

    # --- procesar por día ---------------------------------------------
    df["date"] = df["timestamp"].dt.date
    grouped = df.groupby("date")
    print("📅  Días detectados:", list(grouped.groups))

    equity      = INITIAL_BALANCE
    btc_balance = 0.0
    daily_rows  = []

    for date, trades in grouped:
        day_start = equity

        for _, r in trades.iterrows():
            if r["action"].upper() == "BUY":
                btc_balance += 0.001
                equity      -= 0.001 * r["price"]
            elif r["action"].upper() == "SELL":
                btc_balance -= 0.001
                equity      += 0.001 * r["price"]

        day_end  = equity + btc_balance * trades.iloc[-1]["price"]
        net_ret  = day_end - day_start
        pct_ret  = (net_ret / day_start) * 100 if day_start else 0
        drawdown = (trades["price"].max() - trades["price"].min()) / trades["price"].max() * 100

        daily_rows.append({
            "date"            : date,
            "start_equity"    : round(day_start,  2),
            "end_equity"      : round(day_end,    2),
            "net_return_usdt" : round(net_ret,    2),
            "net_return_pct"  : round(pct_ret,    2),
            "drawdown_pct"    : round(drawdown,   2),
            "num_trades"      : len(trades),
        })

        equity = day_end   # mantener equity acumulada

    # --- guardar -------------------------------------------------------
    pd.DataFrame(daily_rows).to_csv(PERFORMANCE_LOG_PATH, index=False)
    print(f"✅  Rendimiento diario actualizado → {PERFORMANCE_LOG_PATH}")

if __name__ == "__main__":
    calculate_daily_performance()

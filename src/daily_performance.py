# src/daily_performance.py
import pandas as pd
from datetime import datetime
import os

TRADES_PATH = "logs/trades.csv"
PERFORMANCE_LOG_PATH = "logs/performance_log.csv"
INITIAL_BALANCE = 10000.0

def calculate_daily_performance():
    if not os.path.exists(TRADES_PATH):
        print("❌ No se encontró el archivo de trades.")
        return

    trades = pd.read_csv(TRADES_PATH)
    trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True, errors='coerce')
    trades = trades.dropna(subset=["timestamp", "price", "action"]).sort_values("timestamp")

    # Agrupar por día (en UTC)
    trades["date"] = trades["timestamp"].dt.date
    grouped = trades.groupby("date")

    records = []
    equity = INITIAL_BALANCE
    btc_balance = 0.0

    for date, day_trades in grouped:
        day_start_equity = equity

        for _, row in day_trades.iterrows():
            price = row["price"]
            if row["action"] == "BUY":
                btc_balance += 0.001
                equity -= 0.001 * price
            elif row["action"] == "SELL":
                btc_balance -= 0.001
                equity += 0.001 * price

        day_end_equity = equity + (btc_balance * day_trades.iloc[-1]["price"])
        net_return = day_end_equity - day_start_equity
        pct_return = (net_return / day_start_equity) * 100 if day_start_equity > 0 else 0
        drawdown = (day_trades["price"].max() - day_trades["price"].min()) / day_trades["price"].max() * 100

        records.append({
            "date": date,
            "start_equity": round(day_start_equity, 2),
            "end_equity": round(day_end_equity, 2),
            "net_return_usdt": round(net_return, 2),
            "net_return_pct": round(pct_return, 2),
            "drawdown_pct": round(drawdown, 2),
            "num_trades": len(day_trades),
        })

    df_daily = pd.DataFrame(records)
    os.makedirs("logs", exist_ok=True)
    df_daily.to_csv(PERFORMANCE_LOG_PATH, index=False)
    print(f"✅ Rendimiento diario guardado en: {PERFORMANCE_LOG_PATH}")

if __name__ == "__main__":
    calculate_daily_performance()

# src/live_trader.py

import time, os, logging
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timezone

from src.binance_api import get_historical_data
from src.paper_trading import buy, sell, get_price
from src.strategy_selector import select_best_strategy
from src.utils import log_operation        # ← se sigue usando más abajo

load_dotenv()

SYMBOL     = "BTCUSDT"
TIMEFRAME  = "15m"
BOOT_LIMIT = 400                      # ≈4 días (suficiente para SMA/RSI)

# ⏱ convierte "15m", "1h"…  ➜ segundos
unit = TIMEFRAME[-1]
mult = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)

# ── historial inicial ───────────────────────────────────────────────────
history = get_historical_data(SYMBOL, TIMEFRAME, BOOT_LIMIT).to_dict("records")

# 🧠 elige la mejor estrategia PARA ESTE TF
strategy_name, strategy_func, params, _ = select_best_strategy(TIMEFRAME)
logging.basicConfig(filename="logs/live_trader.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logging.info(f"🧠 Estrategia {strategy_name}  TF={TIMEFRAME}  params={params}")

# ── utilidades ──────────────────────────────────────────────────────────
def save_to_csv(row, filename=f"data/{SYMBOL}_{TIMEFRAME}.csv"):
    os.makedirs("data", exist_ok=True)
    file_exists = os.path.isfile(filename)
    pd.DataFrame([row]).to_csv(filename, mode="a", index=False, header=not file_exists)

def fetch_historical_prices():
    last = get_historical_data(SYMBOL, TIMEFRAME, 2).iloc[-1]
    history.append(last.to_dict())
    save_to_csv(last.to_dict())
    df = pd.DataFrame(history)
    return strategy_func(df, **params)

# ── bucle principal ─────────────────────────────────────────────────────
def run_bot():
    position = 0
    while True:
        df = fetch_historical_prices()
        if df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(INTERVAL)
            continue

        last = df.iloc[-1]
        logging.info(f"Precio: {last.close:.2f} | Señal: {last.position}")

        if last.position == 1 and position == 0:
            logging.info("🟢 Señal de COMPRA detectada")
            buy(SYMBOL, last.close, strategy_name, params)
            position = 1

        elif last.position == -1 and position == 1:
            logging.info("🔴 Señal de VENTA detectada")
            sell(SYMBOL, last.close, strategy_name, params)
            position = 0

        time.sleep(INTERVAL)

if __name__ == "__main__":
    run_bot()

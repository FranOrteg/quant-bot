# src/live_trader.py
import time, os, logging
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timezone
from src.binance_api import get_historical_data
from src.paper_trading import buy, sell
from src.strategy_selector import select_best_strategy
from src.utils import log_operation
from src.balance_tracker import load_balance

load_dotenv()

SYMBOL     = "BTCUSDC"          # ← cambia aquí si quieres otro símbolo
TIMEFRAME  = "15m"              # ← cambia aquí si quieres otro TF
BOOT_LIMIT = 400                # ≈4 días de velas para este TF

# -------- intervalo dinámico ------------------------------------------
unit   = TIMEFRAME[-1].lower()
mult   = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)
# ----------------------------------------------------------------------

# historial inicial
history = get_historical_data(SYMBOL, TIMEFRAME, BOOT_LIMIT).to_dict("records")

strategy_name, strategy_func, params, _ = select_best_strategy(tf=TIMEFRAME)

logging.basicConfig(filename="logs/live_trader.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logging.info(f"🧠 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

def save_to_csv(row, filename=f"data/{SYMBOL}_{TIMEFRAME}.csv"):
    os.makedirs("data", exist_ok=True)
    pd.DataFrame([row]).to_csv(filename,
                               mode="a",
                               index=False,
                               header=not os.path.isfile(filename))

def fetch_historical_prices():
    last = get_historical_data(SYMBOL, TIMEFRAME, 2).iloc[-1]
    history.append(last.to_dict())
    save_to_csv(last.to_dict())
    df = pd.DataFrame(history)
    return strategy_func(df, **params)

def run_bot():
    print("🔄 Iniciando bot y cargando balance...")
    balance = load_balance()  # <- Fuerza la carga del balance al arrancar
    print(f"📊 Balance inicial: {balance}")
    position = 0
    while True:
        start_time = time.time()

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

        # Sincronización precisa con el reloj
        elapsed = time.time() - start_time
        sleep_time = max(0, INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_bot()

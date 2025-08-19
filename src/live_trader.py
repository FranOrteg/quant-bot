# src/live_trader.py
import time, os, logging
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timezone

from src.binance_api import get_historical_data

if os.getenv("USE_REAL_TRADING", "False") == "True":
    from src.real_trading import buy, sell
else:
    from src.paper_trading import buy, sell

from src.strategy_selector import select_best_strategy
from src.utils import log_operation
from src.balance_tracker import load_balance, save_balance

load_dotenv()

SYMBOL     = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME  = os.getenv("TRADING_TIMEFRAME", "15m")
BOOT_LIMIT = int(os.getenv("BOOT_LIMIT", "400"))  # ≈ varios días de velas

# -------- intervalo dinámico ------------------------------------------
unit   = TIMEFRAME[-1].lower()
mult   = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)
# ----------------------------------------------------------------------

# === rutas de logs coherentes ===
SUFFIX = f"_{TIMEFRAME}"
TRADES_PATH = f"logs/trades{SUFFIX}.csv"
PERF_PATH   = f"logs/performance_log{SUFFIX}.csv"
DATA_PATH   = f"data/{SYMBOL}_{TIMEFRAME}.csv"

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# historial inicial (EN MEMORIA) y volcado inicial a CSV si no existe
history_df = get_historical_data(SYMBOL, TIMEFRAME, BOOT_LIMIT).reset_index(drop=True)

def _write_boot_history_once():
    """Asegura que el CSV tenga suficiente histórico para cálculos (RSI, SMA…)."""
    if not os.path.exists(DATA_PATH) or os.path.getsize(DATA_PATH) == 0:
        history_df.to_csv(DATA_PATH, index=False)
    else:
        # Sanea y une sin duplicados por timestamp
        try:
            prev = pd.read_csv(DATA_PATH)
            prev["timestamp"] = pd.to_datetime(prev["timestamp"], utc=True, errors="coerce")
            cur  = history_df.copy()
            cur["timestamp"] = pd.to_datetime(cur["timestamp"], utc=True, errors="coerce")
            df = pd.concat([prev, cur], ignore_index=True)
            df = df.dropna(subset=["timestamp"]).drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp")
            for c in ["open","high","low","close","volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)
            df.to_csv(DATA_PATH, index=False)
        except Exception as e:
            # Si falla saneo, reescribe con histórico limpio para evitar NaNs
            history_df.to_csv(DATA_PATH, index=False)

_write_boot_history_once()

# Selección estrategia
strategy_name, strategy_func, params, metrics = select_best_strategy(tf=TIMEFRAME)

logging.basicConfig(filename="logs/live_trader.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logging.info(f"🧐 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

def _append_row_to_csv(row_dict):
    """Añade una vela NUEVA al CSV, evitando duplicados por timestamp."""
    ts = pd.to_datetime(row_dict["timestamp"], utc=True)
    try:
        df = pd.read_csv(DATA_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    except Exception:
        df = pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])

    row = pd.DataFrame([row_dict])
    row["timestamp"] = ts

    df = pd.concat([df, row], ignore_index=True)
    df = df.dropna(subset=["timestamp"]).drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)
    df.to_csv(DATA_PATH, index=False)

def fetch_historical_prices():
    """Trae la última vela cerrada y recalcula la estrategia sobre el histórico EN MEMORIA."""
    last = get_historical_data(SYMBOL, TIMEFRAME, 2).iloc[-1].to_dict()
    # actualiza memoria
    global history_df
    last_ts = pd.to_datetime(last["timestamp"], utc=True)
    history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], utc=True, errors="coerce")
    if last_ts not in set(history_df["timestamp"]):
        history_df = pd.concat([history_df, pd.DataFrame([last])], ignore_index=True)
        history_df = history_df.dropna(subset=["timestamp"]).drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
        _append_row_to_csv(last)  # mantiene el CSV al día

    df = history_df.copy()
    return strategy_func(df, **params)

def run_bot():
    print("🔄 Iniciando bot y cargando balance...")
    balance = load_balance()  # ← Fuerza la carga del balance al arrancar
    print(f"📊 Balance inicial: {balance}")
    save_balance(balance)

    position = 0
    while True:
        start_time = time.time()

        df = fetch_historical_prices()
        if df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(INTERVAL)
            continue

        last = df.iloc[-1]
        # Log enriquecido (incluye nombre de estrategia y params)
        logging.info(f"Precio: {last.close:.2f} | Señal: {int(last.position)} | Strat={strategy_name} | Params={params}")

        if last.position == 1 and position == 0:
            logging.info("🟢 Señal de COMPRA detectada")
            buy(SYMBOL, float(last.close), strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 1

        elif last.position == -1 and position == 1:
            logging.info("🔴 Señal de VENTA detectada")
            sell(SYMBOL, float(last.close), strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 0

        # Sincronización con el reloj del timeframe
        elapsed = time.time() - start_time
        sleep_time = max(0, INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_bot()

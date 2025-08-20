# src/live_trader.py
# Bot en vivo con recarga en caliente de parámetros cuando cambia ACTIVE.

import time, os, logging
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timezone

from src.binance_api import get_historical_data
from src.strategy_selector import select_best_strategy

if os.getenv("USE_REAL_TRADING", "False") == "True":
    from src.real_trading import buy, sell
else:
    from src.paper_trading import buy, sell

from src.utils import log_operation
from src.balance_tracker import load_balance, save_balance

load_dotenv()

SYMBOL     = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME  = os.getenv("TRADING_TIMEFRAME", "15m")
BOOT_LIMIT = int(os.getenv("BOOT_LIMIT", "400"))  # ≈4 días a 15m

# Intervalo dinámico segun TF
unit   = TIMEFRAME[-1].lower()
mult   = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)

# Rutas coherentes de logs
SUFFIX = f"_{TIMEFRAME}"
TRADES_PATH = f"logs/trades{SUFFIX}.csv"
PERF_PATH   = f"logs/performance_log{SUFFIX}.csv"
DATA_PATH   = f"data/{SYMBOL}_{TIMEFRAME}.csv"
ACTIVE_FILE = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(filename="logs/live_trader.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# Historial inicial de velas
history = get_historical_data(SYMBOL, TIMEFRAME, BOOT_LIMIT).to_dict("records")

# Parámetros iniciales (desde selector)
strategy_name, strategy_func, params, metrics = select_best_strategy(symbol=SYMBOL, tf=TIMEFRAME)
logging.info(f"🧐 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

def _active_mtime():
    try:
        return os.path.getmtime(ACTIVE_FILE)
    except FileNotFoundError:
        return None

ACTIVE_MTIME = _active_mtime()

def save_to_csv(row, filename=DATA_PATH):
    # Solo columnas OHLCV + timestamp; proteger contra “basura” en el CSV
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    clean = {k: row[k] for k in cols if k in row}
    pd.DataFrame([clean]).to_csv(filename,
                                 mode="a",
                                 index=False,
                                 header=not os.path.isfile(filename))

def fetch_historical_prices():
    last = get_historical_data(SYMBOL, TIMEFRAME, 2).iloc[-1]
    history.append(last.to_dict())
    save_to_csv(last.to_dict(), DATA_PATH)
    df = pd.DataFrame(history)

    # Saneamos duplicados y orden
    ts_col = "timestamp"
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.dropna(subset=[ts_col])
    df = df.drop_duplicates(subset=ts_col, keep="last").sort_values(ts_col).reset_index(drop=True)

    return strategy_func(df, **params)

def maybe_reload_params(position: int) -> tuple:
    """
    Si ACTIVE cambió y no tenemos posición abierta, recarga estrategia/params.
    Devuelve (reload_hecho: bool, nuevos_params: dict)
    """
    global strategy_name, strategy_func, params, metrics, ACTIVE_MTIME
    mtime = _active_mtime()
    if mtime and ACTIVE_MTIME and mtime == ACTIVE_MTIME:
        return (False, params)

    if mtime and (ACTIVE_MTIME is None or mtime > ACTIVE_MTIME):
        if position != 0:
            # Dejar anotado que hay update pendiente
            logging.info("ℹ️ ACTIVE actualizado pero hay posición abierta; difiriendo hot-reload.")
            return (False, params)
        # Volver a seleccionar (cogerá el ACTIVE)
        strategy_name, strategy_func, params, metrics = select_best_strategy(symbol=SYMBOL, tf=TIMEFRAME)
        ACTIVE_MTIME = mtime
        logging.info(f"♻️ Hot-reload de parámetros: {params}")
        return (True, params)

    return (False, params)

def run_bot():
    print("🔄 Iniciando bot y cargando balance...")
    balance = load_balance()
    print(f"📊 Balance inicial: {balance}")
    save_balance(balance)
    position = 0

    while True:
        start_time = time.time()

        # Hot-reload si procede
        _reloaded, _ = maybe_reload_params(position)

        df = fetch_historical_prices()
        if df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(INTERVAL)
            continue

        last = df.iloc[-1]
        logging.info(f"Precio: {last.close:.2f} | Señal: {last.position} | Strat={strategy_name} | Params={params}")

        if last.position == 1 and position == 0:
            logging.info("🟢 Señal de COMPRA detectada")
            buy(SYMBOL, last.close, strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 1

        elif last.position == -1 and position == 1:
            logging.info("🔴 Señal de VENTA detectada")
            sell(SYMBOL, last.close, strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 0

        # Sincronización precisa con el reloj
        elapsed = time.time() - start_time
        sleep_time = max(0, INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_bot()

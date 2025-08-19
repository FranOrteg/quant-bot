# src/live_trader.py
import os
import time
import logging
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timezone

from src.binance_api import get_historical_data
from src.strategy_selector import select_best_strategy
from src.utils import log_operation
from src.balance_tracker import load_balance, save_balance

# Trading real o paper en función de ENV
if os.getenv("USE_REAL_TRADING", "False") == "True":
    from src.real_trading import buy, sell
else:
    from src.paper_trading import buy, sell

load_dotenv()

# ==================== Config ====================
SYMBOL = os.getenv("TRADING_SYMBOL", "BTCUSDC")  # ← puedes cambiarlo
TIMEFRAME = os.getenv("TRADING_TIMEFRAME", "15m")
BOOT_LIMIT = int(os.getenv("BOOT_LIMIT", "600"))  # ~6 días para 15m

# Intervalo de sincronización dinámico desde el TF
unit = TIMEFRAME[-1].lower()
mult = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)

# Rutas de logs coherentes por TF
SUFFIX = f"_{TIMEFRAME}"
TRADES_PATH = f"logs/trades{SUFFIX}.csv"
PERF_PATH = f"logs/performance_log{SUFFIX}.csv"

# ==================== Logging ====================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/live_trader.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ==================== Inicialización ====================
# Historial inicial
history_df = get_historical_data(SYMBOL, TIMEFRAME, BOOT_LIMIT)

# Detectar columna temporal para deduplicar/ordenar
TS_CANDIDATES = ["open_time", "timestamp", "time", "date"]
ts_col = next((c for c in TS_CANDIDATES if c in history_df.columns), None)

if ts_col:
    history_df = history_df.drop_duplicates(subset=ts_col, keep="last").sort_values(ts_col)

history = history_df.to_dict("records")

# Selección de estrategia
strategy_name, strategy_func, params, _ = select_best_strategy(tf=TIMEFRAME)
logging.info(f"🧐 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

# ==================== Utilidades ====================
def save_to_csv(row: dict, filename: str = None):
    if filename is None:
        filename = f"data/{SYMBOL}_{TIMEFRAME}.csv"
    os.makedirs("data", exist_ok=True)
    pd.DataFrame([row]).to_csv(
        filename,
        mode="a",
        index=False,
        header=not os.path.isfile(filename),
    )


def fetch_historical_prices() -> pd.DataFrame:
    """
    Trae la última vela cerrada, la añade al histórico (deduplicando)
    y devuelve el DataFrame con las columnas de la estrategia aplicadas.
    """
    last_df = get_historical_data(SYMBOL, TIMEFRAME, 2)  # últimas dos velas por seguridad
    last = last_df.iloc[-1].to_dict()

    # Append → dedup → sort
    history.append(last)
    df = pd.DataFrame(history)
    if ts_col:
        df = df.drop_duplicates(subset=ts_col, keep="last").sort_values(ts_col).reset_index(drop=True)

    save_to_csv(last)
    return strategy_func(df, **params)


# ==================== Loop principal ====================
def run_bot():
    print("🔄 Iniciando bot y cargando balance...")
    balance = load_balance()
    print(f"📊 Balance inicial: {balance}")
    save_balance(balance)

    # Estado de posición en memoria (mejorable: persistir/leer de balance/logs)
    position = 0

    while True:
        start_time = time.time()

        df = fetch_historical_prices()

        if df is None or df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(INTERVAL)
            continue

        last = df.iloc[-1]

        try:
            price = float(last.close)
            signal = int(last.position)
        except Exception:
            logging.warning("⚠️ Filas sin campos esperados (close/position)")
            time.sleep(INTERVAL)
            continue

        logging.info(
            f"Precio: {price:.2f} | Señal: {signal} | Strat={strategy_name} | Params={params}"
        )

        # Entrada LONG
        if signal == 1 and position == 0:
            logging.info("🟢 Señal de COMPRA detectada")
            buy(SYMBOL, price, strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 1

        # Cierre de LONG (venta)
        elif signal == -1 and position == 1:
            logging.info("🔴 Señal de VENTA detectada")
            sell(SYMBOL, price, strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 0

        # Sincronización precisa con el reloj de velas
        elapsed = time.time() - start_time
        sleep_time = max(0.0, INTERVAL - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    run_bot()

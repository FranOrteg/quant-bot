# src/live_trader.py

# -*- coding: utf-8 -*-
import time, os, json, logging
from dotenv import load_dotenv
import pandas as pd
from src.binance_api import get_historical_data

# Trading real o paper
if os.getenv("USE_REAL_TRADING", "False") == "True":
    from src.real_trading import buy, sell
else:
    from src.paper_trading import buy, sell

# Selector y utilidades
from src.strategy_selector import select_best_strategy
from src.balance_tracker import load_balance, save_balance

# Para hot‑reload de rsi_sma si cambian parámetros activos:
from src.strategy.rsi_sma import rsi_sma_strategy

load_dotenv()

SYMBOL     = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME  = os.getenv("TRADING_TIMEFRAME", "15m")
BOOT_LIMIT = int(os.getenv("BOOT_LIMIT", "400"))  # ≈4 días para 15m

# -------- intervalo dinámico ------------------------------------------
unit   = TIMEFRAME[-1].lower()
mult   = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)
# ----------------------------------------------------------------------

# === rutas de logs coherentes ===
SUFFIX = f"_{TIMEFRAME}"
TRADES_PATH = f"logs/trades{SUFFIX}.csv"
PERF_PATH   = f"logs/performance_log{SUFFIX}.csv"
ACTIVE_PATH = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"

# historial inicial
history = get_historical_data(SYMBOL, TIMEFRAME, BOOT_LIMIT).to_dict("records")

# estrategia inicial
strategy_name, strategy_func, params, _ = select_best_strategy(symbol=SYMBOL, tf=TIMEFRAME)

logging.basicConfig(filename=f"logs/live_trader{SUFFIX}.log",
                    level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logging.info(f"🧐 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

# Hot reload guard
_last_active_mtime = None

def _maybe_reload_active_params():
    """Si existe results/active_params_{SYMBOL}_{TF}.json y cambia el mtime, recarga en caliente."""
    global strategy_name, strategy_func, params, _last_active_mtime
    try:
        if not os.path.exists(ACTIVE_PATH):
            return
        mtime = os.path.getmtime(ACTIVE_PATH)
        if _last_active_mtime is not None and mtime <= _last_active_mtime:
            return

        with open(ACTIVE_PATH, "r") as f:
            blob = json.load(f)

        best = blob.get("best", {})
        new_params = best.get("params", {})
        new_strategy = best.get("strategy", "rsi_sma")

        # Solo soportamos rsi_sma aquí; amplía si activas otras
        if new_strategy != "rsi_sma":
            new_strategy = "rsi_sma"

        _last_active_mtime = mtime
        strategy_name = new_strategy
        strategy_func = rsi_sma_strategy
        params = dict(
            rsi_period=int(new_params["rsi_period"]),
            sma_period=int(new_params["sma_period"]),
            rsi_buy=int(new_params["rsi_buy"]),
            rsi_sell=int(new_params["rsi_sell"])
        )
        logging.info(f"♻️ Parámetros actualizados en caliente desde {ACTIVE_PATH}: {params}")
        print(f"♻️ Reload params: {params}")
    except Exception as e:
        logging.warning(f"⚠️ No se pudieron recargar parámetros activos: {e}")

def _save_to_csv(row, filename=f"data/{SYMBOL}_{TIMEFRAME}.csv"):
    os.makedirs("data", exist_ok=True)
    pd.DataFrame([row]).to_csv(filename, mode="a", index=False, header=not os.path.isfile(filename))

def _fetch_historical_prices():
    last = get_historical_data(SYMBOL, TIMEFRAME, 2).iloc[-1]
    history.append(last.to_dict())
    _save_to_csv(last.to_dict())
    df = pd.DataFrame(history)
    return strategy_func(df, **params)

def run_bot():
    print("🔄 Iniciando bot y cargando balance...")
    balance = load_balance()  # carga balance (real o simulado)
    print(f"📊 Balance inicial: {balance}")
    save_balance(balance)

    position = 0

    while True:
        start_time = time.time()

        # 1) Hot‑reload de parámetros si cambiaron
        _maybe_reload_active_params()

        # 2) Señales
        df = _fetch_historical_prices()
        if df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(INTERVAL)
            continue

        last = df.iloc[-1]
        logging.info(f"Precio: {last.close:.2f} | Señal: {int(last.position)} | Strat={strategy_name} | Params={params}")

        if last.position == 1 and position == 0:
            buy(SYMBOL, float(last.close), strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 1

        elif last.position == -1 and position == 1:
            sell(SYMBOL, float(last.close), strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 0

        # 3) Sincronización precisa con el reloj
        elapsed = time.time() - start_time
        sleep_time = max(0, INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_bot()

# src/live_trader.py
# -*- coding: utf-8 -*-

import os, time, json, logging, math, hashlib
from dotenv import load_dotenv
import pandas as pd

# ────────────────────────────────────────────────────────────────────────────────
# 1) Cargar .env ANTES de leer variables o elegir modo de trading
# ────────────────────────────────────────────────────────────────────────────────
load_dotenv()

USE_REAL_TRADING = os.getenv("USE_REAL_TRADING", "False") == "True"

# Trading real o paper (elección después de load_dotenv)
if USE_REAL_TRADING:
    from src.real_trading import buy, sell
else:
    from src.paper_trading import buy, sell

# Selector y utilidades
from src.strategy_selector import select_best_strategy
from src.balance_tracker import load_balance, save_balance

# Para hot-reload de rsi_sma si cambian parámetros activos:
from src.strategy.rsi_sma import rsi_sma_strategy

# ────────────────────────────────────────────────────────────────────────────────
# 2) Config básica
# ────────────────────────────────────────────────────────────────────────────────
SYMBOL     = os.getenv("TRADING_SYMBOL", "BTCUSDC")   # para órdenes (python-binance)
TIMEFRAME  = os.getenv("TRADING_TIMEFRAME", "15m")
BOOT_LIMIT = int(os.getenv("BOOT_LIMIT", "400"))      # barras históricas iniciales

def _to_ccxt_symbol(sym: str) -> str:
    """Convierte 'BTCUSDC' → 'BTC/USDC' (ccxt). Si ya tiene '/', lo deja igual."""
    if "/" in sym:
        return sym
    QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "USD")
    for q in QUOTES:
        if sym.endswith(q):
            base = sym[:-len(q)]
            return f"{base}/{q}"
    # Fallback genérico: inserta '/' antes de los últimos 4 caracteres
    return f"{sym[:-4]}/{sym[-4:]}"

CCXT_SYMBOL = _to_ccxt_symbol(SYMBOL)

# Intervalo en segundos a partir del timeframe
unit = TIMEFRAME[-1].lower()
mult = int(TIMEFRAME[:-1])
if unit == "m":
    INTERVAL = mult * 60
elif unit == "h":
    INTERVAL = mult * 3600
elif unit == "d":
    INTERVAL = mult * 86400
else:
    raise ValueError(f"Timeframe no soportado: {TIMEFRAME}")

# Paths coherentes
SUFFIX      = f"_{TIMEFRAME}"
TRADES_PATH = f"logs/trades{SUFFIX}.csv"
PERF_PATH   = f"logs/performance_log{SUFFIX}.csv"
ACTIVE_PATH = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("results", exist_ok=True)

# Logging
logging.basicConfig(
    filename=f"logs/live_trader{SUFFIX}.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ────────────────────────────────────────────────────────────────────────────────
# 3) Datos e iniciativa de estrategia
# ────────────────────────────────────────────────────────────────────────────────
from src.binance_api import get_historical_data  # tras .env y config

# historial inicial (nos quedamos con velas CERRADAS)
_hist_boot = get_historical_data(CCXT_SYMBOL, TIMEFRAME, BOOT_LIMIT + 2)
if len(_hist_boot) >= 1:
    _hist_boot = _hist_boot.iloc[:-1]  # descarta la última por si está en formación
history = _hist_boot.to_dict("records")

# estrategia inicial
strategy_name, strategy_func, params, _ = select_best_strategy(symbol=SYMBOL, tf=TIMEFRAME)
logging.info(f"🧐 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

# ────────────────────────────────────────────────────────────────────────────────
# 4) Hot-reload de parámetros con firma y cooldown
# ────────────────────────────────────────────────────────────────────────────────
_last_active_mtime = None
_last_active_sig   = None
LAST_PARAM_APPLY_TS = 0
PARAM_COOLDOWN_BARS = 12  # no actualizar más de una vez cada X velas

def _params_signature(strategy_name: str, params: dict) -> str:
    core = {"strategy": strategy_name, "params": params}
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(blob.encode()).hexdigest()

try:
    _last_active_sig = _params_signature(strategy_name, params)
except Exception:
    _last_active_sig = None

def _maybe_reload_active_params():
    """Si existe ACTIVE_PATH y cambió, recarga en caliente respetando cooldown y firma."""
    global strategy_name, strategy_func, params
    global _last_active_mtime, _last_active_sig, LAST_PARAM_APPLY_TS

    try:
        if not os.path.exists(ACTIVE_PATH):
            return

        mtime = os.path.getmtime(ACTIVE_PATH)
        if _last_active_mtime is not None and mtime <= _last_active_mtime:
            return

        # respeta cooldown temporal
        now = time.time()
        if now - LAST_PARAM_APPLY_TS < PARAM_COOLDOWN_BARS * INTERVAL:
            return

        with open(ACTIVE_PATH, "r") as f:
            blob = json.load(f)

        best = (blob or {}).get("best", {}) or {}
        new_params   = best.get("params", {}) or {}
        new_strategy = best.get("strategy", "rsi_sma") or "rsi_sma"

        # Por ahora solo rsi_sma
        if new_strategy != "rsi_sma":
            new_strategy = "rsi_sma"

        # Defaults "seguros"
        candidate_params = dict(
            rsi_period=int(new_params.get("rsi_period", 14)),
            sma_period=int(new_params.get("sma_period", 50)),
            rsi_buy=int(new_params.get("rsi_buy", 25)),
            rsi_sell=int(new_params.get("rsi_sell", 75)),
        )

        new_sig = _params_signature(new_strategy, candidate_params)
        if new_sig == _last_active_sig:
            _last_active_mtime = mtime
            return

        # aplica
        _last_active_mtime = mtime
        LAST_PARAM_APPLY_TS = now
        _last_active_sig = new_sig

        strategy_name = new_strategy
        strategy_func = rsi_sma_strategy
        params = candidate_params

        logging.info(f"♻️ Parámetros actualizados en caliente desde {ACTIVE_PATH}: {params}")
        print(f"♻️ Reload params: {params}")
    except Exception as e:
        logging.warning(f"⚠️ No se pudieron recargar parámetros activos: {e}")

# ────────────────────────────────────────────────────────────────────────────────
# 5) Utilidades de datos/tiempo
# ────────────────────────────────────────────────────────────────────────────────
def _save_to_csv(row, filename=f"data/{SYMBOL}_{TIMEFRAME}.csv"):
    pd.DataFrame([row]).to_csv(
        filename, mode="a", index=False, header=not os.path.isfile(filename)
    )

_warned_no_inposition = False

def _fetch_historical_prices(in_position: bool):
    """
    Trae 3 velas, usa la penúltima (CERRADA) y la añade al historial (sin duplicar).
    Luego ejecuta la estrategia con ese DataFrame.
    """
    global _warned_no_inposition

    df2 = get_historical_data(CCXT_SYMBOL, TIMEFRAME, 3)
    if df2 is None or len(df2) < 2:
        return pd.DataFrame()  # insuficiente

    last_closed = df2.iloc[-2]  # penúltima = cerrada
    ts = last_closed.get("timestamp")

    if len(history) == 0 or history[-1].get("timestamp") != ts:
        history.append(last_closed.to_dict())
        # recorta historial para no crecer sin límite (≈2x BOOT_LIMIT)
        if len(history) > BOOT_LIMIT * 3:
            del history[: len(history) - BOOT_LIMIT * 2]
        _save_to_csv(last_closed.to_dict())

    df = pd.DataFrame(history)

    # Intenta pasar in_position; si la estrategia no lo soporta, reintenta sin él
    try:
        return strategy_func(df, in_position=in_position, **params)
    except TypeError:
        if not _warned_no_inposition:
            logging.info("ℹ️ Estrategia no soporta 'in_position'; llamando sin ese argumento.")
            _warned_no_inposition = True
        return strategy_func(df, **params)

def _sleep_until_next_close():
    """
    Sincroniza con el cierre exacto de la siguiente vela.
    Añade +1s de colchón para asegurar que el exchange haya cerrado la barra.
    """
    now = time.time()
    next_close = (math.floor(now / INTERVAL) + 1) * INTERVAL + 1
    sleep_time = max(0, next_close - now)
    time.sleep(sleep_time)

def _get_col(last: pd.Series, *cands):
    """Devuelve la primera columna existente en el orden dado, o NaN."""
    for c in cands:
        if c in last.index:
            return last[c]
    return float("nan")

def _safe_str(x):
    return "" if (isinstance(x, float) and math.isnan(x)) else str(x)

# ────────────────────────────────────────────────────────────────────────────────
# 6) Loop principal
# ────────────────────────────────────────────────────────────────────────────────
def run_bot():
    print("🔄 Iniciando bot y cargando balance...")
    balance = load_balance()      # carga balance (real o simulado)
    print(f"📊 Balance inicial: {balance}")
    save_balance(balance)

    position = 0  # 0=flat, 1=long  (TODO: recuperar estado real si USE_REAL_TRADING)

    while True:
        # 1) Hot-reload de parámetros si cambiaron
        _maybe_reload_active_params()

        # 2) Señales con vela CERRADA
        df = _fetch_historical_prices(in_position=(position == 1))
        if df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            _sleep_until_next_close()
            continue

        last = df.iloc[-1]

        # Determinar acción discreta
        action = "HOLD"
        if last.position == 1 and position == 0:
            action = "BUY"
        elif last.position == -1 and position == 1:
            action = "SELL"

        # logging rico (detecta mayúsculas/minúsculas)
        rsi_v = _get_col(last, "rsi", "RSI")
        sma_v = _get_col(last, "sma", "SMA", f"SMA{params.get('sma_period', 0)}")
        ema_v = _get_col(last, "ema200", "EMA200")
        atrp  = _get_col(last, "atr_pct", "ATR_PCT", "ATR%")
        raw_v = _get_col(last, "signal_raw", "raw_signal", "raw")
        raw   = int(raw_v) if not (isinstance(raw_v, float) and math.isnan(raw_v)) else int(last.position)
        reason = _safe_str(_get_col(last, "reason"))

        logging.info(
            f"Precio: {last.close:.2f} | raw={raw} | action={action} | "
            f"RSI={0 if math.isnan(rsi_v) else float(rsi_v):.1f} | "
            f"SMA{params.get('sma_period', 0)}={0 if math.isnan(sma_v) else float(sma_v):.2f} | "
            f"EMA200={0 if math.isnan(ema_v) else float(ema_v):.2f} | "
            f"ATR%={0 if math.isnan(atrp) else float(atrp):.4f} | "
            f"Strat={strategy_name} | Params={params} | {reason}"
        )

        # 3) Ejecución
        price = float(last.close)
        if action == "BUY":
            buy(SYMBOL, price, strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 1
        elif action == "SELL":
            sell(SYMBOL, price, strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 0

        # 4) Sincronización precisa al cierre de la siguiente vela
        _sleep_until_next_close()

if __name__ == "__main__":
    run_bot()

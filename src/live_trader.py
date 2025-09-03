# src/live_trader.py
# -*- coding: utf-8 -*-

import os
import time
import json
import math
import logging
import hashlib
from dotenv import load_dotenv
import pandas as pd

from src.binance_api import get_historical_data
from src.strategy_selector import select_best_strategy
from src.balance_tracker import load_balance, save_balance
from src.strategy.rsi_sma import rsi_sma_strategy  # estrategia por defecto para hot-reload

# === Carga de entorno =========================================================
load_dotenv()

SYMBOL_ENV   = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME    = os.getenv("TRADING_TIMEFRAME", "15m")
BOOT_LIMIT   = int(os.getenv("BOOT_LIMIT", "400"))  # ~4 días en 15m
USE_REAL_TR  = os.getenv("USE_REAL_TRADING", "False") == "True"

# Trading real o paper (ambos usan símbolo sin barra, p.ej. BTCUSDC)
if USE_REAL_TR:
    from src.real_trading import buy, sell
else:
    from src.paper_trading import buy, sell

# === Utilidades de símbolo (ccxt usa 'BASE/QUOTE'; Binance SDK usa 'BASEQUOTE') ===
def to_ccxt_symbol(sym: str) -> str:
    if "/" in sym:
        return sym
    # intenta dividir por sufijos comunes
    QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "TUSD", "BTC", "ETH", "EUR", "TRY")
    for q in QUOTES:
        if sym.endswith(q):
            base = sym[:-len(q)]
            return f"{base}/{q}"
    return sym  # fallback

def to_binance_symbol(sym: str) -> str:
    return sym.replace("/", "")

SYMBOL_CCXT   = to_ccxt_symbol(SYMBOL_ENV)     # p.ej. "BTC/USDC"
SYMBOL_TRADE  = to_binance_symbol(SYMBOL_ENV)  # p.ej. "BTCUSDC"

# === Intervalo dinámico (segundos por vela) ==================================
unit = TIMEFRAME[-1].lower()
mult = int(TIMEFRAME[:-1])
INTERVAL = mult * (60 if unit == "m" else 3600)

# === Paths de logs coherentes por timeframe ===================================
SUFFIX      = f"_{TIMEFRAME}"
TRADES_PATH = f"logs/trades{SUFFIX}.csv"
PERF_PATH   = f"logs/performance_log{SUFFIX}.csv"
ACTIVE_PATH = f"results/active_params_{to_binance_symbol(SYMBOL_CCXT)}_{TIMEFRAME}.json"

# === Logging =================================================================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=f"logs/live_trader{SUFFIX}.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# === Historial inicial (solo barras cerradas) =================================
history = get_historical_data(SYMBOL_CCXT, TIMEFRAME, BOOT_LIMIT).to_dict("records")

# === Estrategia inicial =======================================================
strategy_name, strategy_func, params, _ = select_best_strategy(
    symbol=to_binance_symbol(SYMBOL_CCXT), tf=TIMEFRAME
)
logging.info(f"🧐 Estrategia {strategy_name}   TF={TIMEFRAME}   params={params}")

# === Hot-reload guard / firmas de params =====================================
_last_active_mtime = None
_last_active_sig   = None

def _params_signature(name: str, p: dict) -> str:
    core = {"strategy": name, "params": p}
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(blob.encode()).hexdigest()

try:
    _last_active_sig = _params_signature(strategy_name, params)
except Exception:
    _last_active_sig = None

LAST_PARAM_APPLY_TS = 0
PARAM_COOLDOWN_BARS = 12  # evita cambios de params demasiado frecuentes

def _maybe_reload_active_params():
    """
    Si existe ACTIVE_PATH y cambió su mtime, recarga en caliente la estrategia/params
    respetando un cooldown de PARAM_COOLDOWN_BARS velas. Acepta parámetros extra
    numéricos del JSON (p.ej., lookback_bars) y los preserva.
    """
    global strategy_name, strategy_func, params, _last_active_mtime, _last_active_sig, LAST_PARAM_APPLY_TS

    try:
        if not os.path.exists(ACTIVE_PATH):
            return

        mtime = os.path.getmtime(ACTIVE_PATH)
        if _last_active_mtime is not None and mtime <= _last_active_mtime:
            return

        # cooldown por número de velas
        now = time.time()
        if now - LAST_PARAM_APPLY_TS < PARAM_COOLDOWN_BARS * INTERVAL:
            return

        with open(ACTIVE_PATH, "r") as f:
            blob = json.load(f)

        best = blob.get("best", {})
        new_params   = best.get("params", {}) or {}
        new_strategy = best.get("strategy", "rsi_sma") or "rsi_sma"

        # por ahora solo rsi_sma en live
        if new_strategy != "rsi_sma":
            new_strategy = "rsi_sma"

        # base obligatoria
        applied_params = dict(
            rsi_period=int(new_params.get("rsi_period", 14)),
            sma_period=int(new_params.get("sma_period", 50)),
            rsi_buy=int(new_params.get("rsi_buy", 25)),
            rsi_sell=int(new_params.get("rsi_sell", 75)),
        )
        # merge de extras numéricos (p.ej. lookback_bars)
        for k, v in new_params.items():
            if k in applied_params:
                continue
            # solo pasamos valores escalares numéricos (int/float) y seguros de castear
            try:
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.', '', 1).lstrip('-').isdigit()):
                    iv = int(v) if str(v).isdigit() else float(v)
                    applied_params[k] = iv
            except Exception:
                pass  # ignoramos lo que no sea numérico

        new_sig = _params_signature(new_strategy, applied_params)
        if _last_active_sig is not None and new_sig == _last_active_sig:
            _last_active_mtime = mtime
            return  # mismo payload efectivo; silencio

        # Aplica
        strategy_name = new_strategy
        strategy_func = rsi_sma_strategy
        params        = applied_params
        _last_active_mtime = mtime
        _last_active_sig   = new_sig
        LAST_PARAM_APPLY_TS = now

        logging.info(f"♻️ Parámetros actualizados en caliente desde {ACTIVE_PATH}: {params}")
        print(f"♻️ Reload params: {params}")

    except Exception as e:
        logging.warning(f"⚠️ No se pudieron recargar parámetros activos: {e}")



# === Persistencia incremental de datos =======================================
def _save_to_csv(row: dict, filename: str = f"data/{to_binance_symbol(SYMBOL_CCXT)}_{TIMEFRAME}.csv"):
    os.makedirs("data", exist_ok=True)
    pd.DataFrame([row]).to_csv(
        filename, mode="a", index=False, header=not os.path.isfile(filename)
    )

# === Fetch de la última barra cerrada + aplicación de estrategia =============
def _fetch_historical_prices(in_position: bool) -> pd.DataFrame:
    """
    Trae la última barra cerrada y la añade a 'history' solo si es nueva.
    Luego aplica la estrategia con los 'params' activos.
    """
    last_df = get_historical_data(SYMBOL_CCXT, TIMEFRAME, 2)
    last = last_df.iloc[-1].to_dict()

    if not history or last["timestamp"] != history[-1]["timestamp"]:
        history.append(last)
        _save_to_csv(last)
        # recorta para no crecer sin límite
        if len(history) > BOOT_LIMIT + 1000:
            del history[: len(history) - (BOOT_LIMIT + 1000)]

    df = pd.DataFrame(history)
    # pasar estado de posición para reglas dependientes (stop_bar, etc.)
    return strategy_func(df, in_position=in_position, **params)

# === Bucle principal ==========================================================
def run_bot():
    print(f"🔄 Iniciando bot ({'REAL' if USE_REAL_TR else 'PAPER'}) para {SYMBOL_TRADE} @ {TIMEFRAME}")
    balance = load_balance()
    print(f"📊 Balance inicial: {balance}")
    save_balance(balance)

    position = 0  # 0=flat, 1=long

    while True:
        start_time = time.time()

        # 1) Hot-reload de parámetros si cambiaron
        _maybe_reload_active_params()

        # 2) Señales
        df = _fetch_historical_prices(in_position=(position == 1))
        if df.empty or "position" not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(INTERVAL)
            continue

        last = df.iloc[-1]

        # determina acción
        action = "HOLD"
        if last.position == 1 and position == 0:
            action = "BUY"
        elif last.position == -1 and position == 1:
            action = "SELL"

        # logging rico con tolerancia a NaN
        rsi_v = getattr(last, "rsi", float("nan"))
        sma_v = getattr(last, "sma", float("nan"))
        ema_v = getattr(last, "ema200", float("nan"))
        raw   = int(getattr(last, "signal_raw", last.position))

        logging.info(
            f"Precio: {last.close:.2f} | raw={raw} "
            f"RSI={0 if math.isnan(rsi_v) else rsi_v:.1f} | "
            f"SMA{params.get('sma_period', '')}={0 if math.isnan(sma_v) else sma_v:.2f} | "
            f"EMA200={0 if math.isnan(ema_v) else ema_v:.2f} | "
            f"Action={action} "
        )

        # 3) Ejecuta trade si corresponde
        if action == "BUY":
            buy(SYMBOL_TRADE, float(last.close), strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 1

        elif action == "SELL":
            sell(SYMBOL_TRADE, float(last.close), strategy_name, params, TRADES_PATH, PERF_PATH)
            position = 0

        # 4) Sincronización precisa con el reloj de vela
        elapsed = time.time() - start_time
        time.sleep(max(0, INTERVAL - elapsed))


if __name__ == "__main__":
    run_bot()

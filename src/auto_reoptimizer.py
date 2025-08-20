# src/auto_reoptimizer.py
# Re-optimiza RSI+SMA de forma periódica y publica el mejor set en:
#   results/active_params_<SYMBOL>_<TIMEFRAME>.json
#
# ENV principales (con defaults razonables):
#   REOPT_SYMBOL=BTCUSDC
#   REOPT_TIMEFRAME=15m
#   REOPT_LIMIT=5000
#   REOPT_EVERY_HOURS=12
#   REOPT_MIN_IMPROVEMENT=0.002   # 0.2% de mejora mínima del retorno para reemplazar
#   ACTIVE_STALE_HOURS=48         # si el active_params está más viejo, forzar update

import os, time, json, logging, tempfile
from datetime import datetime, timezone, timedelta
import pandas as pd
from dotenv import load_dotenv

from src.binance_api import get_historical_data
from src.strategy.rsi_sma import rsi_sma_strategy
from src.backtest import backtest_signals

load_dotenv()

SYMBOL     = os.getenv("REOPT_SYMBOL",     os.getenv("TRADING_SYMBOL", "BTCUSDC"))
TIMEFRAME  = os.getenv("REOPT_TIMEFRAME",  "15m")
LIMIT      = int(os.getenv("REOPT_LIMIT",  "5000"))
EVERY_HRS  = float(os.getenv("REOPT_EVERY_HOURS", "12"))
MIN_IMPROV = float(os.getenv("REOPT_MIN_IMPROVEMENT", "0.002"))  # 0.2%
STALE_HRS  = float(os.getenv("ACTIVE_STALE_HOURS", "48"))

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

CSV_FILE   = os.path.join(RESULTS_DIR, f"rsi_optimization_{TIMEFRAME}.csv")
BEST_FILE  = os.path.join(RESULTS_DIR, f"best_rsi_{TIMEFRAME}.json")
ACTIVE_FILE= os.path.join(RESULTS_DIR, f"active_params_{SYMBOL}_{TIMEFRAME}.json")

logging.basicConfig(
    filename="logs/auto_reoptimizer.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _robust_sort(df: pd.DataFrame) -> pd.DataFrame:
    # Orden principal por retorno, secundario por Sharpe y por menor drawdown (abs)
    return df.sort_values(
        by=["total_return", "sharpe_ratio", "max_drawdown"],
        ascending=[False, False, True]  # drawdown más alto negativo → True
    )

def _atomic_write_json(path: str, data: dict):
    fd, tmp = tempfile.mkstemp(prefix=".tmp_active_", dir=os.path.dirname(path) or ".")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def _file_mtime(path: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except FileNotFoundError:
        return None

def _load_json(path: str) -> dict | None:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def grid_candidates():
    # Puedes tunear esta malla si quieres más/exhaustivo (cuidado con el tiempo de cómputo)
    rsi_periods     = [10, 14, 21]
    sma_periods     = [15, 20, 30]
    rsi_buys        = [30, 35, 40]
    rsi_sells       = [60, 65, 70]
    for rp in rsi_periods:
        for sp in sma_periods:
            for rb in rsi_buys:
                for rs in rsi_sells:
                    if rb >= rs:
                        continue
                    yield dict(rsi_period=rp, sma_period=sp, rsi_buy=rb, rsi_sell=rs)

def run_once():
    logging.info(f"⚙️ Re-optimizando {SYMBOL} {TIMEFRAME} (LIM={LIMIT}) …")
    df = get_historical_data(SYMBOL, TIMEFRAME, LIMIT)
    if df is None or df.empty:
        logging.warning("❌ No hay datos para optimizar.")
        return

    results = []
    for params in grid_candidates():
        dfx = rsi_sma_strategy(df.copy(), **params)
        dfx, capital, metrics = backtest_signals(dfx, timeframe=TIMEFRAME)
        results.append({
            "strategy": "rsi_sma",
            **params,
            "capital_final": round(capital, 2),
            "total_return": round(metrics["total_return"] * 100, 2),
            "sharpe_ratio": round(metrics["sharpe_ratio"], 2),
            "max_drawdown": round(metrics["max_drawdown"] * 100, 2),
            "timestamp": _now_iso()
        })

    res = pd.DataFrame(results)
    res.to_csv(CSV_FILE, index=False)

    res_sorted = _robust_sort(res)
    best_row = res_sorted.iloc[0].to_dict()

    best_payload = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "data_end": str(df["timestamp"].iloc[-1]),
        "generated_at": _now_iso(),
        "best": {
            "params": {
                "rsi_period": int(best_row["rsi_period"]),
                "sma_period": int(best_row["sma_period"]),
                "rsi_buy": int(best_row["rsi_buy"]),
                "rsi_sell": int(best_row["rsi_sell"]),
            },
            "metrics": {
                "total_return_pct": float(best_row["total_return"]),
                "sharpe_ratio": float(best_row["sharpe_ratio"]),
                "max_drawdown_pct": float(best_row["max_drawdown"]),
            },
            "source": "auto_reoptimizer"
        }
    }

    # Comparar contra ACTIVE actual (si existe)
    active = _load_json(ACTIVE_FILE)
    should_update = False
    reason = "first_write"

    if active is None:
        should_update = True
    else:
        # Criterio: staleness o mejora mínima de retorno
        active_mtime = _file_mtime(ACTIVE_FILE)
        if active_mtime and (datetime.now(timezone.utc) - active_mtime) > timedelta(hours=STALE_HRS):
            should_update = True
            reason = "stale_active"
        else:
            old_ret = float(active.get("best", {}).get("metrics", {}).get("total_return_pct", 0))
            new_ret = float(best_payload["best"]["metrics"]["total_return_pct"])
            if (new_ret - old_ret) / max(1.0, abs(old_ret)) >= MIN_IMPROV:
                should_update = True
                reason = "improved_return"

    # Guardar BEST_FILE siempre (histórico de “mejor por backtest actual”), ACTIVE solo si procede
    _atomic_write_json(BEST_FILE, best_payload)
    if should_update:
        _atomic_write_json(ACTIVE_FILE, best_payload)
        logging.info(f"✅ ACTIVE actualizado ({reason}): {best_payload['best']['params']}")
    else:
        logging.info("ℹ️ ACTIVE no actualizado (sin mejora o no stale).")

def main_loop():
    logging.info(f"🚀 Auto-reoptimizer ON  symbol={SYMBOL}  tf={TIMEFRAME}  every={EVERY_HRS}h")
    while True:
        try:
            run_once()
        except Exception as e:
            logging.exception(f"❌ Error en re-optimización: {e}")
        time.sleep(max(60, int(EVERY_HRS * 3600)))  # dormimos entre runs

if __name__ == "__main__":
    main_loop()

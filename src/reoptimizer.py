# src/reoptimizer.py

# -*- coding: utf-8 -*-
"""
Reoptimizer para PM2:
- Cada ciclo:
  1) Comprueba si el CSV results/rsi_optimization_{TF}.csv está viejo (mtime) o vacío.
  2) Si está viejo (o forzado), lanza la optimización (subproceso) con los mismos parámetros que usarías en CLI.
  3) Lee el CSV y escoge el mejor set por total_return.
  4) Escribe results/active_params_{SYMBOL}_{TF}.json con el mejor set.
  5) Añade una línea de histórico en results/active_params_history_{SYMBOL}_{TF}.csv
- Maneja fallos sin crashear.
"""

import os
import time
import json
import subprocess
import pandas as pd
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

SYMBOL           = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME        = os.getenv("TRADING_TIMEFRAME", "15m")
# Frecuencia del loop (segundos)
REOPT_EVERY_MIN  = int(os.getenv("REOPT_EVERY_MIN", "60"))
SLEEP_SECONDS    = int(os.getenv("REOPT_SLEEP_SECONDS", str(REOPT_EVERY_MIN * 60)))
# Límite de velas para la optimización
REOPT_LIMIT      = int(os.getenv("REOPT_LIMIT", "8000"))
# Umbral de "obsolescencia" del CSV (en minutos)
CSV_STALE_MIN    = int(os.getenv("REOPT_CSV_STALE_MIN", "60"))

OPT_CSV      = f"results/rsi_optimization_{TIMEFRAME}.csv"
ACTIVE_JSON  = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"
HISTORY_CSV  = f"results/active_params_history_{SYMBOL}_{TIMEFRAME}.csv"

def _params_signature(payload: dict) -> str:
    """
    Firma estable solo con lo que nos importa para decidir reescritura:
    estrategia + params (ignora 'generated_at', 'metrics' y demás).
    """
    best = payload.get("best", {})
    core = {
        "strategy": best.get("strategy"),
        "params": best.get("params"),
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(blob.encode()).hexdigest()

def _mtime_minutes(path: str):
    try:
        mtime = os.path.getmtime(path)
        age_sec = max(0, time.time() - mtime)
        return age_sec / 60.0
    except Exception:
        return 1e9  # muy viejo

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _run_optimizer():
    """
    Lanza la optimización equivalente a:
      python -m src.optimize_rsi --symbol SYMBOL --timeframe TIMEFRAME --limit REOPT_LIMIT
    """
    cmd = [
        ".venv/bin/python", "-m", "src.optimize_rsi",
        "--symbol", SYMBOL,
        "--timeframe", TIMEFRAME,
        "--limit", str(REOPT_LIMIT)
    ]
    print(f"🚀 Lanzando optimización: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=os.getcwd(), check=True)
        print("✅ Optimización terminada")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Optimización falló: {e}")

def _pick_best_from_csv(path: str):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    for c in ["total_return","sharpe_ratio","max_drawdown"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["total_return"])
    if df.empty:
        return None
    best = df.sort_values("total_return", ascending=False).iloc[0]
    params = dict(
        rsi_period=int(best["rsi_period"]),
        sma_period=int(best["sma_period"]),
        rsi_buy=int(best["rsi_buy"]),
        rsi_sell=int(best["rsi_sell"]),
    )
    metrics = dict(
        total_return=float(best["total_return"]),
        sharpe_ratio=float(best["sharpe_ratio"]),
        max_drawdown=float(best["max_drawdown"]),
    )
    payload = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "data_end": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best": {
            "strategy": "rsi_sma",
            "params": params,
            "metrics": {
                "total_return_pct": metrics["total_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown_pct": metrics["max_drawdown"],
            },
        },
    }
    return payload

def _append_history(payload: dict):
    try:
        _ensure_dir(HISTORY_CSV)
        row = {
            "ts": payload.get("generated_at"),
            "symbol": payload.get("symbol"),
            "timeframe": payload.get("timeframe"),
            "strategy": payload["best"].get("strategy", "rsi_sma"),
            "rsi_period": payload["best"]["params"]["rsi_period"],
            "sma_period": payload["best"]["params"]["sma_period"],
            "rsi_buy": payload["best"]["params"]["rsi_buy"],
            "rsi_sell": payload["best"]["params"]["rsi_sell"],
            "total_return_pct": payload["best"]["metrics"]["total_return_pct"],
            "sharpe_ratio": payload["best"]["metrics"]["sharpe_ratio"],
            "max_drawdown_pct": payload["best"]["metrics"]["max_drawdown_pct"],
        }
        pd.DataFrame([row]).to_csv(HISTORY_CSV, mode="a", index=False, header=not os.path.isfile(HISTORY_CSV))
    except Exception as e:
        print(f"⚠️ No se pudo escribir histórico: {e}")

def main_loop():
    print(f"🔁 Reoptimizer activo para {SYMBOL} {TIMEFRAME}. CSV: {OPT_CSV} | cada {SLEEP_SECONDS}s")
    last_sig_path = ACTIVE_JSON + ".hash"
    last_sig = None

    # Inicializa firma desde .hash o desde JSON existente
    if os.path.exists(last_sig_path):
        try:
            last_sig = open(last_sig_path, "r").read().strip() or None
        except Exception:
            last_sig = None
    elif os.path.exists(ACTIVE_JSON):
        try:
            with open(ACTIVE_JSON, "r") as f:
                existing = json.load(f)
            last_sig = _params_signature(existing)
            with open(last_sig_path, "w") as f:
                f.write(last_sig)
        except Exception:
            last_sig = None

    while True:
        try:
            # 1) Asegurar que el CSV esté fresco (o generarlo)
            csv_age_min = _mtime_minutes(OPT_CSV)
            must_optimize = (not os.path.exists(OPT_CSV)) or (csv_age_min > CSV_STALE_MIN)

            if must_optimize:
                print(f"🧪 CSV ausente/viejo ({csv_age_min:.1f} min) → optimizando…")
                _run_optimizer()

            # 2) Elegir el mejor set desde el CSV
            best = _pick_best_from_csv(OPT_CSV)
            if best is None:
                print(f"⏳ No hay CSV válido aún: {OPT_CSV}")
            else:
                os.makedirs("results", exist_ok=True)
                new_sig = _params_signature(best)

                if new_sig != last_sig:
                    with open(ACTIVE_JSON, "w") as f:
                        f.write(json.dumps(best, sort_keys=True))
                    with open(last_sig_path, "w") as f:
                        f.write(new_sig)
                    last_sig = new_sig
                    _append_history(best)
                    print(f"✅ Actualizado {ACTIVE_JSON} → {best['best']['params']}")
                else:
                    print("👍 Sin cambios en strategy/params; no se reescribe.")
        except Exception as e:
            print(f"⚠️ Reoptimizer warning: {e}")

        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main_loop()

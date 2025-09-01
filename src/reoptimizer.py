# src/reoptimizer.py

# -*- coding: utf-8 -*-
"""
Reoptimizer para PM2:
- Cada ciclo:
  1) Comprueba si el CSV results/rsi_optimization_{TF}.csv está viejo (mtime) o vacío.
  2) Si está viejo (o forzado), lanza la optimización (subproceso).
  3) Lee el CSV y escoge el mejor set por total_return.
  4) Escribe results/active_params_{SYMBOL}_{TF}.json solo si cambian strategy/params (hash).
  5) Añade una línea de histórico en results/active_params_history_{SYMBOL}_{TF}.csv
- Maneja fallos sin crashear.
"""

import os
import time
import json
import hashlib
import subprocess
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ===================== Config ===================== #
SYMBOL            = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME         = os.getenv("TRADING_TIMEFRAME", "15m")
REOPT_EVERY_MIN   = int(os.getenv("REOPT_EVERY_MIN", "60"))
SLEEP_SECONDS     = int(os.getenv("REOPT_SLEEP_SECONDS", str(REOPT_EVERY_MIN * 60)))
REOPT_LIMIT       = int(os.getenv("REOPT_LIMIT", "8000"))          # velas para optimización
CSV_STALE_MIN     = int(os.getenv("REOPT_CSV_STALE_MIN", "60"))    # umbral antigüedad CSV (min)
REOPT_FORCE       = os.getenv("REOPT_FORCE", "False") == "True"    # forzar optimización en cada ciclo
PYTHON_BIN        = os.getenv("PYTHON_BIN", ".venv/bin/python")    # binario de python para subproceso

OPT_CSV      = f"results/rsi_optimization_{TIMEFRAME}.csv"
ACTIVE_JSON  = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"
ACTIVE_HASH  = f"{ACTIVE_JSON}.hash"
HISTORY_CSV  = f"results/active_params_history_{SYMBOL}_{TIMEFRAME}.csv"
# ================================================== #


# -------------------- Utilidades -------------------- #
def _ensure_dir_for_file(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _mtime_minutes(path: str) -> float:
    try:
        age_sec = max(0, time.time() - os.path.getmtime(path))
        return age_sec / 60.0
    except Exception:
        return 1e9  # muy viejo o no existe

def _params_signature(payload: dict) -> str:
    """
    Firma estable basada SOLO en strategy + params, ignorando timestamps/metrics.
    """
    best = payload.get("best", {})
    core = {"strategy": best.get("strategy"), "params": best.get("params")}
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(blob.encode()).hexdigest()

def _run_optimizer():
    """
    Ejecuta: python -m src.optimize_rsi --symbol SYMBOL --timeframe TIMEFRAME --limit REOPT_LIMIT
    """
    cmd = [
        PYTHON_BIN, "-m", "src.optimize_rsi",
        "--symbol", SYMBOL,
        "--timeframe", TIMEFRAME,
        "--limit", str(REOPT_LIMIT),
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

    # coerción de tipos y limpieza mínima
    for c in ("total_return", "sharpe_ratio", "max_drawdown"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    required_cols = {"rsi_period", "sma_period", "rsi_buy", "rsi_sell", "total_return"}
    if not required_cols.issubset(df.columns):
        print(f"⚠️ CSV sin columnas requeridas: faltan {required_cols - set(df.columns)}")
        return None

    df = df.dropna(subset=["total_return"])
    if df.empty:
        return None

    best = df.sort_values("total_return", ascending=False).iloc[0]

    # construir payload normalizado
    params = dict(
        rsi_period=int(best["rsi_period"]),
        sma_period=int(best["sma_period"]),
        rsi_buy=int(best["rsi_buy"]),
        rsi_sell=int(best["rsi_sell"]),
    )
    metrics = dict(
        total_return=float(best.get("total_return", 0.0)),
        sharpe_ratio=float(best.get("sharpe_ratio", 0.0)) if "sharpe_ratio" in df.columns else 0.0,
        max_drawdown=float(best.get("max_drawdown", 0.0)) if "max_drawdown" in df.columns else 0.0,
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
        _ensure_dir_for_file(HISTORY_CSV)
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
        pd.DataFrame([row]).to_csv(
            HISTORY_CSV, mode="a", index=False, header=not os.path.isfile(HISTORY_CSV)
        )
    except Exception as e:
        print(f"⚠️ No se pudo escribir histórico: {e}")
# ---------------------------------------------------- #


def main_loop():
    print(f"🔁 Reoptimizer activo para {SYMBOL} {TIMEFRAME}. CSV: {OPT_CSV} | cada {SLEEP_SECONDS}s")

    # Inicializa la firma previa desde .hash o desde el JSON existente
    last_sig = None
    if os.path.exists(ACTIVE_HASH):
        try:
            last_sig = open(ACTIVE_HASH, "r").read().strip() or None
        except Exception:
            last_sig = None
    elif os.path.exists(ACTIVE_JSON):
        try:
            with open(ACTIVE_JSON, "r") as f:
                existing = json.load(f)
            last_sig = _params_signature(existing)
            _ensure_dir_for_file(ACTIVE_HASH)
            with open(ACTIVE_HASH, "w") as f:
                f.write(last_sig)
        except Exception:
            last_sig = None

    while True:
        try:
            # 1) Asegura frescura del CSV o fuerza optimización
            csv_age_min = _mtime_minutes(OPT_CSV)
            must_optimize = REOPT_FORCE or (not os.path.exists(OPT_CSV)) or (csv_age_min > CSV_STALE_MIN)

            if must_optimize:
                msg = "forzado" if REOPT_FORCE else f"viejo ({csv_age_min:.1f} min)"
                print(f"🧪 CSV {msg} → ejecutando optimización…")
                _run_optimizer()

            # 2) Selecciona mejor set
            best = _pick_best_from_csv(OPT_CSV)
            if best is None:
                print(f"⏳ No hay CSV válido aún: {OPT_CSV}")
            else:
                new_sig = _params_signature(best)

                if new_sig != last_sig:
                    # solo reescribir si cambia strategy/params
                    _ensure_dir_for_file(ACTIVE_JSON)
                    with open(ACTIVE_JSON, "w") as f:
                        # sort_keys para estabilidad, separators para JSON compacto
                        f.write(json.dumps(best, sort_keys=True, separators=(",", ":")))
                    _ensure_dir_for_file(ACTIVE_HASH)
                    with open(ACTIVE_HASH, "w") as f:
                        f.write(new_sig)
                    last_sig = new_sig
                    _append_history(best)
                    print(f"✅ Actualizado {ACTIVE_JSON} → {best['best']['params']}")
                else:
                    print("👍 Sin cambios en strategy/params; no se reescribe.")

        except Exception as e:
            print(f"⚠️ Reoptimizer warning: {e}")

        # pequeño jitter para evitar sincronización perfecta entre procesos
        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main_loop()

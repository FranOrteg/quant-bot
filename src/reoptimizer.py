# src/reoptimizer.py
# -*- coding: utf-8 -*-
"""
Reoptimizer con quality-gate:
- Cada ciclo:
  1) Comprueba si el CSV results/rsi_optimization_{TF}.csv está viejo o no existe.
  2) Si está viejo (o forzado), lanza la optimización (subproceso).
  3) Lee el CSV y escoge el mejor set por total_return.
  4) Aplica QUALITY GATE (min retorno, min Sharpe, max DD).
  5) Escribe results/active_params_{SYMBOL}_{TF}.json solo si pasan el gate y cambian strategy/params.
  6) Añade histórico en results/active_params_history_{SYMBOL}_{TF}.csv
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
REOPT_LIMIT       = int(os.getenv("REOPT_LIMIT", "8000"))
CSV_STALE_MIN     = int(os.getenv("REOPT_CSV_STALE_MIN", "60"))
REOPT_FORCE       = os.getenv("REOPT_FORCE", "False").strip() == "True"
PYTHON_BIN        = os.getenv("PYTHON_BIN", ".venv/bin/python")

# --- Quality gate (umbrales mínimos para promover nuevos params) ---
# NOTA: Los campos del CSV están en porcentaje para return y drawdown (p.ej. 1.75, -2.14)
MIN_RET_PCT   = float(os.getenv("REOPT_MIN_RETURN_PCT", "0"))   # p.ej. 0  (>= 0%)
MIN_SHARPE    = float(os.getenv("REOPT_MIN_SHARPE", "0"))       # p.ej. 0  (>= 0)
MAX_DD_PCT    = float(os.getenv("REOPT_MAX_DD_PCT", "20"))      # p.ej. 20 (DD debe ser >= -20%)

OPT_CSV      = f"results/rsi_optimization_{TIMEFRAME}.csv"
ACTIVE_JSON  = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"
ACTIVE_HASH  = f"{ACTIVE_JSON}.hash"
HISTORY_CSV  = f"results/active_params_history_{SYMBOL}_{TIMEFRAME}.csv"
# ================================================== #


# -------------------- Utilidades -------------------- #
def _log(msg: str):
    print(f"{datetime.now(timezone.utc).isoformat()}: {msg}")

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

def _passes_gate(payload: dict):
    """
    Verifica que el candidato cumpla los umbrales configurados.
    Retorna (ok: bool, reason: str)
    """
    m = payload["best"]["metrics"]
    ret = float(m.get("total_return_pct", 0.0))   # % (ej. 1.75)
    shr = float(m.get("sharpe_ratio", 0.0))
    dd  = float(m.get("max_drawdown_pct", 0.0))   # % negativo (ej. -2.14)

    if ret < MIN_RET_PCT:
        return False, f"return {ret:.2f}% < min {MIN_RET_PCT:.2f}%"
    if shr < MIN_SHARPE:
        return False, f"sharpe {shr:.2f} < min {MIN_SHARPE:.2f}"
    if dd < -abs(MAX_DD_PCT):
        return False, f"drawdown {dd:.2f}% < min {-abs(MAX_DD_PCT):.2f}%"
    return True, "ok"

def _run_optimizer():
    cmd = [
        PYTHON_BIN, "-m", "src.optimize_rsi",
        "--symbol", SYMBOL,
        "--timeframe", TIMEFRAME,
        "--limit", str(REOPT_LIMIT),
    ]
    _log(f"🚀 Lanzando optimización: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=os.getcwd(), check=True)
        _log("✅ Optimización terminada")
    except subprocess.CalledProcessError as e:
        _log(f"⚠️ Optimización falló: {e}")

def _pick_best_from_csv(path: str):
    if not os.path.exists(path):
        return None

    df = pd.read_csv(path)
    if df.empty:
        return None

    # Coerción de tipos
    for c in ("total_return", "sharpe_ratio", "max_drawdown"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    required = {"rsi_period", "sma_period", "rsi_buy", "rsi_sell", "total_return"}
    if not required.issubset(df.columns):
        _log(f"⚠️ CSV sin columnas requeridas: faltan {required - set(df.columns)}")
        return None

    df = df.dropna(subset=["total_return"]).copy()
    if df.empty:
        return None

    # QUALITY GATE rápido a nivel de DataFrame (max_drawdown está en % negativo)
    passed = df[
        (df["total_return"] >= MIN_RET_PCT) &
        (df["sharpe_ratio"] >= MIN_SHARPE) &
        (df["max_drawdown"] >= -abs(MAX_DD_PCT))
    ]
    if passed.empty:
        _log(
            "⛔ Ninguna configuración pasó el quality gate → "
            f"min_return={MIN_RET_PCT}% min_sharpe={MIN_SHARPE} maxDD=-{abs(MAX_DD_PCT)}%"
        )
        return None

    best = passed.sort_values("total_return", ascending=False).iloc[0]

    params = dict(
        rsi_period=int(best["rsi_period"]),
        sma_period=int(best["sma_period"]),
        rsi_buy=int(best["rsi_buy"]),
        rsi_sell=int(best["rsi_sell"]),
    )
    metrics = dict(
        total_return=float(best.get("total_return", 0.0)),
        sharpe_ratio=float(best.get("sharpe_ratio", 0.0)),
        max_drawdown=float(best.get("max_drawdown", 0.0)),
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
        "quality_gate": {
            "min_return_pct": MIN_RET_PCT,
            "min_sharpe": MIN_SHARPE,
            "max_drawdown_pct": MAX_DD_PCT,
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
        _log(f"⚠️ No se pudo escribir histórico: {e}")
# ---------------------------------------------------- #


def main_loop():
    _log(
        f"🔁 Reoptimizer activo para {SYMBOL} {TIMEFRAME}. "
        f"CSV: {OPT_CSV} | cada {SLEEP_SECONDS}s | Gate: "
        f"min_ret={MIN_RET_PCT}% min_sharpe={MIN_SHARPE} maxDD=-{abs(MAX_DD_PCT)}%"
    )

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
                _log(f"🧪 CSV {msg} → ejecutando optimización…")
                _run_optimizer()

            # 2) Selecciona mejor set que pase el gate
            best = _pick_best_from_csv(OPT_CSV)
            if best is None:
                _log("👉 No hay candidato que pase el gate; se mantiene el activo.")
            else:
                new_sig = _params_signature(best)
                if new_sig != last_sig:
                    # Doble verificación del gate a nivel de payload (por si el CSV cambia de formato)
                    ok, reason = _passes_gate(best)
                    if not ok:
                        _log(f"🚫 Nuevo set no supera el gate → {reason}. No se promueve.")
                    else:
                        _ensure_dir_for_file(ACTIVE_JSON)
                        with open(ACTIVE_JSON, "w") as f:
                            f.write(json.dumps(best, sort_keys=True, separators=(",", ":")))
                        _ensure_dir_for_file(ACTIVE_HASH)
                        with open(ACTIVE_HASH, "w") as f:
                            f.write(new_sig)
                        last_sig = new_sig
                        _append_history(best)
                        _log(f"✅ Actualizado {ACTIVE_JSON} → {best['best']['params']}")
                else:
                    _log("👍 Sin cambios en strategy/params; no se reescribe.")

        except Exception as e:
            _log(f"⚠️ Reoptimizer warning: {e}")

        # pequeño sleep entre ciclos
        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main_loop()

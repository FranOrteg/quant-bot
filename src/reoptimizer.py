# src/reoptimizer.py
# -*- coding: utf-8 -*-
"""
Reoptimizer con quality-gate y fallback opcional:
- Cada ciclo:
  1) Comprueba si el CSV results/rsi_optimization_{TF}.csv está viejo o no existe.
  2) Si está viejo (o forzado), lanza la optimización (subproceso).
  3) Lee el CSV y escoge el mejor set por total_return que PASE EL GATE.
     *Opcional*: si nadie pasa el gate y REOPT_ALLOW_ABS_FALLBACK=True, usa el Top ABS.
  4) Escribe results/active_params_{SYMBOL}_{TF}.json solo si cambian strategy/params.
  5) Añade histórico en results/active_params_history_{SYMBOL}_{TF}.csv
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

# Quality gate (métricas en % como en optimize_rsi)
MIN_RETURN_PCT    = float(os.getenv("REOPT_MIN_RETURN_PCT", "0.0"))  # ej 0.5
MIN_SHARPE        = float(os.getenv("REOPT_MIN_SHARPE", "0.0"))      # ej 0.2
MAX_DRAWDOWN_PCT  = float(os.getenv("REOPT_MAX_DD_PCT", "20.0"))     # ej 15 → DD >= -15%

# Fallback: si nadie pasa el gate, ¿usar el mejor absoluto?
ALLOW_ABS_FALLBACK = os.getenv("REOPT_ALLOW_ABS_FALLBACK", "False").strip().lower() in ("1", "true", "yes", "on")

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
        return 1e9

def _params_signature(payload: dict) -> str:
    best = payload.get("best", {})
    core = {"strategy": best.get("strategy"), "params": best.get("params")}
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(blob.encode()).hexdigest()

def _run_optimizer():
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
    """
    Lee el CSV y devuelve (payload, status).
    status ∈ {'ok_gate', 'fallback_abs', 'no_csv', 'empty_csv', 'missing_cols',
              'no_rows', 'no_pass_gate'}
    """
    if not os.path.exists(path):
        return None, "no_csv"

    df = pd.read_csv(path)
    if df.empty:
        return None, "empty_csv"

    # Tipos numéricos (convertimos si existen estas columnas)
    for c in ("total_return", "sharpe_ratio", "max_drawdown",
              "lookback_bars", "rsi_period", "sma_period", "rsi_buy", "rsi_sell"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    required = {"rsi_period", "sma_period", "rsi_buy", "rsi_sell", "total_return"}
    if not required.issubset(df.columns):
        return None, f"missing_cols:{required - set(df.columns)}"

    df = df.dropna(subset=["total_return"]).copy()
    if df.empty:
        return None, "no_rows"

    # --- QUALITY GATE (max_drawdown suele venir negativo) ---
    passed = df[
        (df["total_return"] >= MIN_RETURN_PCT) &
        (df["sharpe_ratio"] >= MIN_SHARPE) &
        (df["max_drawdown"] >= -abs(MAX_DRAWDOWN_PCT))
    ]

    use_fallback = False
    if passed.empty:
        print(
            "⛔ Ningún setup pasó el gate → "
            f"min_return={MIN_RETURN_PCT}%, min_sharpe={MIN_SHARPE}, maxDD=-{abs(MAX_DRAWDOWN_PCT)}%"
        )
        if not ALLOW_ABS_FALLBACK:
            return None, "no_pass_gate"
        print("↩️ REOPT_ALLOW_ABS_FALLBACK=on → usando Top ABS por total_return.")
        candidate = df.sort_values("total_return", ascending=False).iloc[0]
        use_fallback = True
    else:
        candidate = passed.sort_values("total_return", ascending=False).iloc[0]

    # construir params (obligatorios + lookback_bars si existe)
    params = dict(
        rsi_period=int(candidate["rsi_period"]),
        sma_period=int(candidate["sma_period"]),
        rsi_buy=int(candidate["rsi_buy"]),
        rsi_sell=int(candidate["rsi_sell"]),
    )
    if "lookback_bars" in candidate.index and not pd.isna(candidate["lookback_bars"]):
        params["lookback_bars"] = int(candidate["lookback_bars"])

    metrics = dict(
        total_return=float(candidate.get("total_return", 0.0)),
        sharpe_ratio=float(candidate.get("sharpe_ratio", 0.0)) if "sharpe_ratio" in df.columns else 0.0,
        max_drawdown=float(candidate.get("max_drawdown", 0.0)) if "max_drawdown" in df.columns else 0.0,
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
            "min_return_pct": MIN_RETURN_PCT,
            "min_sharpe": MIN_SHARPE,
            "max_drawdown_pct": MAX_DRAWDOWN_PCT,
            "allow_abs_fallback": ALLOW_ABS_FALLBACK,
            "selection_mode": "fallback_abs" if use_fallback else "gate",
        },
    }
    return payload, ("fallback_abs" if use_fallback else "ok_gate")


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
            "lookback_bars": payload["best"]["params"].get("lookback_bars", None),
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
    print(
        f"🔁 Reoptimizer activo para {SYMBOL} {TIMEFRAME}. "
        f"CSV: {OPT_CSV} | cada {SLEEP_SECONDS}s | Gate: "
        f"min_ret={MIN_RETURN_PCT}% min_sharpe={MIN_SHARPE} maxDD=-{abs(MAX_DRAWDOWN_PCT)}% "
        f"| fallback_abs={'on' if ALLOW_ABS_FALLBACK else 'off'}"
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
            csv_age_min = _mtime_minutes(OPT_CSV)
            must_optimize = REOPT_FORCE or (not os.path.exists(OPT_CSV)) or (csv_age_min > CSV_STALE_MIN)

            if must_optimize:
                msg = "forzado" if REOPT_FORCE else f"viejo ({csv_age_min:.1f} min)"
                print(f"🧪 CSV {msg} → ejecutando optimización…")
                _run_optimizer()

            best, status = _pick_best_from_csv(OPT_CSV)
            if best is None:
                print(f"👉 Sin candidato (status={status}); se mantiene el activo.")
            else:
                new_sig = _params_signature(best)
                if new_sig != last_sig:
                    _ensure_dir_for_file(ACTIVE_JSON)
                    with open(ACTIVE_JSON, "w") as f:
                        f.write(json.dumps(best, sort_keys=True, separators=(",", ":")))
                    _ensure_dir_for_file(ACTIVE_HASH)
                    with open(ACTIVE_HASH, "w") as f:
                        f.write(new_sig)
                    last_sig = new_sig
                    _append_history(best)
                    mode = best.get("quality_gate", {}).get("selection_mode", "gate")
                    print(f"✅ Actualizado {ACTIVE_JSON} (mode={mode}) → {best['best']['params']}")
                else:
                    print("👍 Sin cambios en strategy/params; no se reescribe.")

        except Exception as e:
            print(f"⚠️ Reoptimizer warning: {e}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main_loop()

# src/strategy_selector.py
# -*- coding: utf-8 -*-
import os
import json
import pandas as pd
from dotenv import load_dotenv

from src.strategy.rsi_sma import rsi_sma_strategy

load_dotenv()

MIN_RETURN_PCT   = float(os.getenv("REOPT_MIN_RETURN_PCT", "0.0"))
MIN_SHARPE       = float(os.getenv("REOPT_MIN_SHARPE", "0.0"))
MAX_DRAWDOWN_PCT = float(os.getenv("REOPT_MAX_DD_PCT", "99.0"))

def _num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return float(default)

def _passes_gate(metrics: dict) -> bool:
    # soporta tanto *_pct como sin sufijo (por compat)
    ret  = _num(metrics.get("total_return_pct", metrics.get("total_return", -1e9)))
    shrp = _num(metrics.get("sharpe_ratio", -1e9))
    dd   = _num(metrics.get("max_drawdown_pct", metrics.get("max_drawdown", -1e9)))
    return (ret >= MIN_RETURN_PCT) and (shrp >= MIN_SHARPE) and (dd >= -abs(MAX_DRAWDOWN_PCT))

def _read_active_params(symbol: str, tf: str):
    path = f"results/active_params_{symbol}_{tf}.json"
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            blob = json.load(f)
        best    = blob.get("best", {})
        params  = best.get("params", {})
        metrics = best.get("metrics", {})
        strat   = best.get("strategy", "rsi_sma")

        if not _passes_gate(metrics):
            print(f"⚠️ ACTIVE_PARAMS no pasa el gate ({metrics}). Se ignora.")
            return None

        return dict(strategy=strat, params=params, metrics=metrics, source="ACTIVE_PARAMS_JSON", path=path)
    except Exception as e:
        print(f"⚠️ Error leyendo {path}: {e}")
        return None

def _best_from_csv(path: str, strat: str, param_cols):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None

    for c in ["total_return", "sharpe_ratio", "max_drawdown"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Quality gate sobre el CSV (total_return está en %)
    df = df.dropna(subset=["total_return"]).copy()
    df = df[
        (df["total_return"] >= MIN_RETURN_PCT) &
        (df["sharpe_ratio"] >= MIN_SHARPE) &
        (df["max_drawdown"] >= -abs(MAX_DRAWDOWN_PCT))
    ]
    if df.empty:
        print("⚠️ CSV sin filas que pasen el gate.")
        return None

    best = df.sort_values("total_return", ascending=False).iloc[0]
    params = {}
    for k in param_cols:
        v = best[k]
        try:
            params[k] = int(v)
        except Exception:
            params[k] = _num(v, v)

    metrics = dict(
        total_return=_num(best.get("total_return", 0)),
        sharpe_ratio=_num(best.get("sharpe_ratio", 0)),
        max_drawdown=_num(best.get("max_drawdown", 0)),
    )
    return dict(strategy=strat, params=params, metrics=metrics, source=path)

def select_best_strategy(symbol: str = "BTCUSDC", tf: str = "15m"):
    # 1) Activo (si pasa el gate)
    active = _read_active_params(symbol, tf)
    if active:
        strategy_name = "rsi_sma"
        mapper = {"rsi_sma": rsi_sma_strategy}
        print("\n🏆 Estrategia seleccionada")
        print("   • Nombre     :", strategy_name)
        print("   • Parámetros :", active["params"])
        print("   • Métricas   :", active["metrics"])
        print("   • Fuente     :", f"{active['source']} ✅")
        return strategy_name, mapper[strategy_name], active["params"], active["metrics"]

    # 2) CSV (si pasa el gate)
    suf = f"_{tf}" if tf else ""
    rsi_csv = f"results/rsi_optimization{suf}.csv"
    rsi_best = _best_from_csv(rsi_csv, "rsi_sma", ["rsi_period", "sma_period", "rsi_buy", "rsi_sell"])

    if rsi_best:
        mapper = {"rsi_sma": rsi_sma_strategy}
        print("\n🏆 Estrategia seleccionada")
        print("   • Nombre     :", rsi_best["strategy"])
        print("   • Parámetros :", rsi_best["params"])
        print("   • Métricas   :", rsi_best["metrics"])
        print("   • Fuente     :", f"{rsi_best['source']} ✅")
        return rsi_best["strategy"], mapper[rsi_best["strategy"]], rsi_best["params"], rsi_best["metrics"]

    # 3) Fallback seguro si nada pasa el gate
    fallback_params = {"rsi_period": 14, "sma_period": 50, "rsi_buy": 30, "rsi_sell": 70}
    fallback_metrics = {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "score": 0.0}
    print("\n🏆 Estrategia seleccionada")
    print("   • Nombre     : rsi_sma")
    print("   • Parámetros :", fallback_params)
    print("   • Métricas   :", fallback_metrics)
    print("   • Fuente     : FALLBACK_GENERIC ✅")
    return "rsi_sma", rsi_sma_strategy, fallback_params, fallback_metrics

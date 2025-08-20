# src/strategy_selector.py

import os
import json
import time
import pandas as pd

# Exportadas en src/strategy/__init__.py
from src.strategy import rsi_sma_strategy, macd_strategy, moving_average_crossover

FRESH_SECONDS = 48 * 3600  # consideramos "reciente" <= 48h

def _now():
    return int(time.time())

def _mtime(path: str) -> int:
    try:
        return int(os.path.getmtime(path))
    except Exception:
        return 0

def _print_choice(source: str, name: str, params: dict, metrics: dict):
    print("\n🏆 Estrategia seleccionada")
    print(f"   • Nombre     : {name}")
    print(f"   • Parámetros : {params}")
    print(f"   • Métricas   : {metrics}")
    print(f"   • Fuente     : {source} ✅")

def _score_row(row: pd.Series) -> tuple:
    """
    Orden robusto: mayor retorno, mayor Sharpe, menor drawdown absoluto.
    Nota: en tus CSV 'total_return' y 'max_drawdown' vienen en %, Sharpe sin %.
    """
    ret = float(row.get("total_return", 0.0))
    sharpe = float(row.get("sharpe_ratio", 0.0))
    mdd = abs(float(row.get("max_drawdown", 0.0)))
    # sort descending by ret, sharpe; ascending by abs(mdd)
    return (ret, sharpe, -mdd)

def _pick_best_from_csv(csv_path: str):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    if df.empty:
        return None

    # Filtramos sólo rsi_sma (tu bot opera con ella en vivo)
    df = df[df["strategy"] == "rsi_sma"].copy()
    if df.empty:
        return None

    # Orden robusto
    df["__sort1__"] = df.apply(_score_row, axis=1)
    df = df.sort_values("__sort1__", ascending=False)

    best = df.iloc[0]
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
    return ("rsi_sma", params, metrics, "rsi_optimization CSV")

def _pick_best_from_json(json_path: str):
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        best = data.get("best", {})
        params = best.get("params", {})
        metrics_in = best.get("metrics", {})
        # Nombres uniformes para impresión
        metrics = dict(
            total_return=metrics_in.get("total_return_pct", None),
            sharpe_ratio=metrics_in.get("sharpe_ratio", None),
            max_drawdown=metrics_in.get("max_drawdown_pct", None),
        )
        # Validación mínima de campos
        need = {"rsi_period","sma_period","rsi_buy","rsi_sell"}
        if not need.issubset(set(params.keys())):
            return None
        return ("rsi_sma", params, metrics, "best_rsi JSON")
    except Exception:
        return None

def select_best_strategy(tf: str = "15m"):
    """
    Devuelve: (strategy_name, strategy_func, params, metrics)
    Prioridad: results/best_rsi_{tf}.json (si es reciente) -> results/rsi_optimization_{tf}.csv -> fallback seguro.
    """
    suf = tf
    results_dir = "results"
    json_path = os.path.join(results_dir, f"best_rsi_{suf}.json")
    csv_path  = os.path.join(results_dir, f"rsi_optimization_{suf}.csv")

    # 1) Intentar JSON si es reciente
    cand = None
    if os.path.exists(json_path):
        age = _now() - _mtime(json_path)
        if age <= FRESH_SECONDS:
            cand = _pick_best_from_json(json_path)

    # 2) Si no hay JSON utilizable, usar CSV
    if cand is None:
        cand = _pick_best_from_csv(csv_path)

    # 3) Fallback ultra-conservador
    if cand is None:
        cand = (
            "rsi_sma",
            {"rsi_period": 21, "sma_period": 30, "rsi_buy": 40, "rsi_sell": 70},
            {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0},
            "fallback interno"
        )

    name, params, metrics, source = cand

    mapper = dict(
        rsi_sma=rsi_sma_strategy,
        macd=macd_strategy,
        moving_average=moving_average_crossover
    )

    _print_choice(
        "best_rsi.json" if "JSON" in source else source,
        name, params, metrics
    )
    return (name, mapper[name], params, metrics)

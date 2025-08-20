# -*- coding: utf-8 -*-
"""
Selector de estrategia y parámetros
- Prioriza parámetros activos desde results/active_params_{SYMBOL}_{TF}.json
- Si no existen, elige el mejor de results/*_optimization_{TF}.csv
- Fallback seguro a RSI+SMA con parámetros conservadores
"""

import os
import json
import pandas as pd

# Importa SOLO lo que existe en tu repo:
from src.strategy.rsi_sma import rsi_sma as rsi_sma_strategy  # si tu función se llama rsi_sma
# Si tu función se llama rsi_sma_strategy, descomenta esta línea y comenta la anterior:
# from src.strategy.rsi_sma import rsi_sma_strategy

# Si usas otras estrategias, descomenta cuando las uses:
# from src.strategy.macd import macd_strategy
# from src.strategy.multi_indicator import multi_indicator_strategy


def _num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return float(default)


def _read_active_params(symbol: str, tf: str):
    """Lee results/active_params_{symbol}_{tf}.json si existe."""
    path = f"results/active_params_{symbol}_{tf}.json"
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            blob = json.load(f)
        best = blob.get("best", {})
        params = best.get("params", {})
        metrics = best.get("metrics", {})
        strat = best.get("strategy", "rsi_sma")
        return dict(strategy=strat, params=params, metrics=metrics, source="ACTIVE_PARAMS_JSON", path=path)
    except Exception:
        return None


def _best_from_csv(path: str, strat: str, param_cols):
    """Busca el mejor registro por total_return en un CSV de resultados."""
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None

    # Asegurar tipos numéricos
    for c in ["total_return", "sharpe_ratio", "max_drawdown"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["total_return"])
    if df.empty:
        return None

    best = df.sort_values("total_return", ascending=False).iloc[0]
    params = {k: int(best[k]) if str(best[k]).isdigit() else _num(best[k], best[k]) for k in param_cols}
    metrics = dict(
        total_return=_num(best.get("total_return", 0)),
        sharpe_ratio=_num(best.get("sharpe_ratio", 0)),
        max_drawdown=_num(best.get("max_drawdown", 0))
    )
    return dict(strategy=strat, params=params, metrics=metrics, source=path)


def select_best_strategy(symbol: str = "BTCUSDC", tf: str = "15m"):
    """
    Orden de prioridad:
    1) results/active_params_{symbol}_{tf}.json   (si existe)
    2) results/rsi_optimization_{tf}.csv          (mejor por total_return)
    3) Fallback conservador
    """
    # 1) Activo
    active = _read_active_params(symbol, tf)
    if active:
        strategy_name = active["strategy"]
        if strategy_name != "rsi_sma":
            # Si en un futuro quieres activar MACD o multi_indicator, añade el mapper debajo
            strategy_name = "rsi_sma"
        mapper = {"rsi_sma": rsi_sma_strategy}
        print("\n🏆 Estrategia seleccionada")
        print("   • Nombre     :", strategy_name)
        print("   • Parámetros :", active["params"])
        print("   • Métricas   :", active["metrics"])
        print("   • Fuente     :", f"{active['source']} ✅")
        return strategy_name, mapper[strategy_name], active["params"], active["metrics"]

    # 2) CSVs
    suf = f"_{tf}" if tf else ""
    rsi_csv = f"results/rsi_optimization{suf}.csv"
    rsi_best = _best_from_csv(rsi_csv, "rsi_sma", ["rsi_period", "sma_period", "rsi_buy", "rsi_sell"])

    candidates = [c for c in [rsi_best] if c]
    if candidates:
        best = candidates[0]
        mapper = {"rsi_sma": rsi_sma_strategy}
        print("\n🏆 Estrategia seleccionada")
        print("   • Nombre     :", best["strategy"])
        print("   • Parámetros :", best["params"])
        print("   • Métricas   :", best["metrics"])
        print("   • Fuente     :", f"{best['source']} ✅")
        return best["strategy"], mapper[best["strategy"]], best["params"], best["metrics"]

    # 3) Fallback seguro
    fallback_params = {"rsi_period": 14, "sma_period": 50, "rsi_buy": 30, "rsi_sell": 70}
    fallback_metrics = {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "score": 0.0}
    print("\n🏆 Estrategia seleccionada")
    print("   • Nombre     : rsi_sma")
    print("   • Parámetros :", fallback_params)
    print("   • Métricas   :", fallback_metrics)
    print("   • Fuente     : FALLBACK_GENERIC ✅")
    return "rsi_sma", rsi_sma_strategy, fallback_params, fallback_metrics

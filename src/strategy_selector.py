# src/strategy_selector.py
# Selector de estrategia que prioriza ACTIVE params y hace fallback a CSV/JSON.

import os, json, pandas as pd
from datetime import datetime, timezone, timedelta

# Importa funciones reales de estrategia
from src.strategy.rsi_sma import rsi_sma_strategy
from src.strategy.macd import macd_strategy
from src.strategy.hybrid_strategy import hybrid_strategy as moving_average_crossover  # si lo usas

RESULTS_DIR = "results"

def _file_mtime(path: str):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except FileNotFoundError:
        return None

def _load_json(path: str):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def _best_from_csv(csv_path: str):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    if df.empty:
        return None
    # orden robusto
    df = df.sort_values(by=["total_return", "sharpe_ratio", "max_drawdown"],
                        ascending=[False, False, True])
    r = df.iloc[0]
    return dict(
        strategy="rsi_sma",
        params=dict(
            rsi_period=int(r["rsi_period"]),
            sma_period=int(r["sma_period"]),
            rsi_buy=int(r["rsi_buy"]),
            rsi_sell=int(r["rsi_sell"]),
        ),
        metrics=dict(
            total_return=float(r["total_return"]),
            sharpe_ratio=float(r["sharpe_ratio"]),
            max_drawdown=float(r["max_drawdown"]),
        ),
        source="csv"
    )

def select_best_strategy(symbol="BTCUSDC", tf="15m",
                         prefer_active=True, active_stale_hours=48):
    """
    Prioriza results/active_params_<SYMBOL>_<TF>.json si existe y no está stale.
    Fallbacks:
      1) results/best_rsi_<TF>.json
      2) results/rsi_optimization_<TF>.csv
      3) default razonable
    """
    suf = f"_{tf}"
    active_file = os.path.join(RESULTS_DIR, f"active_params_{symbol}_{tf}.json")
    best_file   = os.path.join(RESULTS_DIR, f"best_rsi_{tf}.json")
    csv_file    = os.path.join(RESULTS_DIR, f"rsi_optimization_{tf}.csv")

    # 1) ACTIVE
    if prefer_active and os.path.exists(active_file):
        mtime = _file_mtime(active_file)
        if not mtime or (datetime.now(timezone.utc) - mtime) <= timedelta(hours=active_stale_hours):
            j = _load_json(active_file)
            if j and "best" in j and "params" in j["best"]:
                params = j["best"]["params"]
                metrics = j["best"].get("metrics", {})
                source = j["best"].get("source", "active")
                print("\n🏆 Estrategia seleccionada (ACTIVE)")
                print("   • Nombre     : rsi_sma")
                print("   • Parámetros :", params)
                print("   • Métricas   :", metrics)
                print("   • Fuente     :", f"{os.path.basename(active_file)} ✅")
                return ("rsi_sma", rsi_sma_strategy, params, metrics)

    # 2) BEST JSON
    bj = _load_json(best_file)
    if bj and "best" in bj and "params" in bj["best"]:
        params = bj["best"]["params"]
        metrics = bj["best"].get("metrics", {})
        print("\n🏆 Estrategia seleccionada (BEST JSON)")
        print("   • Nombre     : rsi_sma")
        print("   • Parámetros :", params)
        print("   • Métricas   :", metrics)
        print("   • Fuente     :", f"{os.path.basename(best_file)} ✅")
        return ("rsi_sma", rsi_sma_strategy, params, metrics)

    # 3) CSV
    csv_best = _best_from_csv(csv_file)
    if csv_best:
        print("\n🏆 Estrategia seleccionada (CSV)")
        print("   • Nombre     :", csv_best["strategy"])
        print("   • Parámetros :", csv_best["params"])
        print("   • Métricas   :", csv_best["metrics"])
        print("   • Fuente     :", f"{os.path.basename(csv_file)} ✅")
        return ("rsi_sma", rsi_sma_strategy, csv_best["params"], csv_best["metrics"])

    # 4) Fallback seguro
    fallback_params = dict(rsi_period=14, sma_period=20, rsi_buy=40, rsi_sell=70)
    print("\n🏆 Estrategia seleccionada (FALLBACK)")
    print("   • Nombre     : rsi_sma")
    print("   • Parámetros :", fallback_params)
    print("   • Métricas   : {}")
    print("   • Fuente     : DEFAULT ⚠️")
    return ("rsi_sma", rsi_sma_strategy, fallback_params, {})

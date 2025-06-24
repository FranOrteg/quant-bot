# src/strategy_selector.py
import os
import pandas as pd
from src.strategy import moving_average_crossover, rsi_sma_strategy, macd_strategy

# --- ① preset “ganador” ---------------------------------------------------
PRESET_OPTIMAL = {
    "rsi_sma": {
        "params": {"rsi_period": 14, "sma_period": 10,
                   "rsi_buy": 30, "rsi_sell": 70},
        "metrics": {"total_return": 0.0524}   # opcional
    }
}
# -------------------------------------------------------------------------

# Convierte cualquier tipo numpy a int o float estándar
def convert_types(params):
    return {k: int(v) if isinstance(v, (int, float)) else v for k, v in params.items()}

def get_best_from_csv(path, strategy_name, param_names):
    if not os.path.exists(path):
        return None                # ← si aún no hay CSV
    df = pd.read_csv(path)
    if df.empty:
        return None
    best_row = df.sort_values("total_return", ascending=False).iloc[0]
    params  = {k: best_row[k] for k in param_names}
    metrics = dict(total_return=float(best_row["total_return"]),
                   sharpe_ratio=float(best_row["sharpe_ratio"]),
                   max_drawdown=float(best_row["max_drawdown"]))
    return {"strategy": strategy_name,
            "params": convert_types(params),
            "metrics": metrics}


def select_best_strategy():
    # --- ② primero la receta óptima --------------------------------------
    if "rsi_sma" in PRESET_OPTIMAL:
        p = PRESET_OPTIMAL["rsi_sma"]
        return ("rsi_sma", rsi_sma_strategy, p["params"], p["metrics"])
    # ---------------------------------------------------------------------

    # … mismo código que ya tenías para leer los CSV ----------------------
    candidates = [
        get_best_from_csv("results/sma_optimization.csv",  "moving_average", ["short_window","long_window"]),
        get_best_from_csv("results/rsi_optimization.csv",  "rsi_sma",        ["rsi_period","sma_period","rsi_buy","rsi_sell"]),
        get_best_from_csv("results/macd_optimization.csv", "macd",           ["short_ema","long_ema","signal_ema"]),
    ]
    candidates = [c for c in candidates if c]        # filtra None
    best = max(candidates, key=lambda x: x["metrics"]["total_return"])

    strategy_map = {
        "moving_average": moving_average_crossover,
        "rsi_sma": rsi_sma_strategy,
        "macd": macd_strategy
    }

    print("\n🏆 Estrategia ganadora:")
    print(f"🔹 Nombre: {best['strategy']}")
    print(f"🔹 Parámetros: {best['params']}")
    print(f"🔹 Métricas: {best['metrics']}")

    return best["strategy"], strategy_map[best["strategy"]], best["params"], best["metrics"]

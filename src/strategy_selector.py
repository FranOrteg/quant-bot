# src/strategy_selector.py

import pandas as pd

def get_best_from_csv(path, strategy_name, param_names):
    df = pd.read_csv(path)
    best_row = df.sort_values("total_return", ascending=False).iloc[0]
    return {
        "strategy": strategy_name,
        "params": {k: best_row[k] for k in param_names},
        "metrics": {
            "total_return": best_row["total_return"],
            "sharpe_ratio": best_row["sharpe_ratio"],
            "max_drawdown": best_row["max_drawdown"],
        }
    }

def select_best_strategy():
    candidates = [
        get_best_from_csv("results/sma_optimization.csv", "moving_average", ["short_window", "long_window"]),
        get_best_from_csv("results/rsi_optimization.csv", "rsi_sma", ["rsi_period", "sma_period", "rsi_buy", "rsi_sell"]),
        get_best_from_csv("results/macd_optimization.csv", "macd", ["short_ema", "long_ema", "signal_ema"]),
    ]

    # Selección: puedes cambiar el criterio aquí
    best = max(candidates, key=lambda x: x["metrics"]["total_return"])

    print("\n🏆 Estrategia ganadora:")
    print(f"🔹 Nombre: {best['strategy']}")
    print(f"🔹 Parámetros: {best['params']}")
    print(f"🔹 Métricas: {best['metrics']}")
    return best

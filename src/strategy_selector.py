# src/strategy_selector.py

import pandas as pd
from src.strategy import moving_average_crossover, rsi_sma_strategy, macd_strategy

# Convierte cualquier tipo numpy a int o float estándar
def convert_types(params):
    return {k: int(v) if isinstance(v, (int, float)) or 'period' in k or 'ema' in k else v for k, v in params.items()}

def get_best_from_csv(path, strategy_name, param_names):
    df = pd.read_csv(path)
    best_row = df.sort_values("total_return", ascending=False).iloc[0]

    params = {k: best_row[k] for k in param_names}
    metrics = {
        "total_return": float(best_row["total_return"]),
        "sharpe_ratio": float(best_row["sharpe_ratio"]),
        "max_drawdown": float(best_row["max_drawdown"]),
    }

    return {
        "strategy": strategy_name,
        "params": convert_types(params),
        "metrics": metrics,
    }

def select_best_strategy():
    candidates = [
        get_best_from_csv("results/sma_optimization.csv", "moving_average", ["short_window", "long_window"]),
        get_best_from_csv("results/rsi_optimization.csv", "rsi_sma", ["rsi_period", "sma_period", "rsi_buy", "rsi_sell"]),
        get_best_from_csv("results/macd_optimization.csv", "macd", ["short_ema", "long_ema", "signal_ema"]),
    ]

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

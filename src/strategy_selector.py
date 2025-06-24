# src/strategy_selector.py

import os, pandas as pd
from src.strategy import moving_average_crossover, rsi_sma_strategy, macd_strategy

# ── preset «por defecto» si no hay CSV ────────────────────────────────
PRESET_OPTIMAL = {
    "rsi_sma": dict(params=dict(rsi_period=14, sma_period=10,
                                rsi_buy=30,  rsi_sell=70),
                    metrics=dict(total_return=0.00,
                                 sharpe_ratio=0.0,
                                 max_drawdown=0.0))
}
# ───────────────────────────────────────────────────────────────────────

def _convert(v):               # np.int64 → int
    return int(v) if isinstance(v, (int, float)) else v

def _best_from_csv(path, strat, param_cols):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    best = df.sort_values("total_return", ascending=False).iloc[0]
    return dict(strategy=strat,
                params={k: _convert(best[k]) for k in param_cols},
                metrics=dict(total_return=float(best.total_return),
                             sharpe_ratio=float(best.sharpe_ratio),
                             max_drawdown=float(best.max_drawdown)))

def select_best_strategy(tf="1h"):
    suf = f"_{tf}" if tf != "1h" else ""
    cands = [
        _best_from_csv(f"results/sma_optimization{suf}.csv",
                       "moving_average", ["short_window", "long_window"]),
        _best_from_csv(f"results/rsi_optimization{suf}.csv",
                       "rsi_sma", ["rsi_period", "sma_period",
                                   "rsi_buy",  "rsi_sell"]),
        _best_from_csv(f"results/macd_optimization{suf}.csv",
                       "macd", ["short_ema", "long_ema", "signal_ema"])
    ]
    cands = [c for c in cands if c]

    # ← fallback si aún está vacío
    if not cands:
        preset = PRESET_OPTIMAL["rsi_sma"]
        cands = [dict(strategy="rsi_sma", **preset)]

    best = max(cands, key=lambda x: x["metrics"]["total_return"])

    mapper = dict(moving_average=moving_average_crossover,
                  rsi_sma=rsi_sma_strategy,
                  macd=macd_strategy)

    print("\n🏆 Estrategia ganadora")
    print("   • Nombre     :", best["strategy"])
    print("   • Parámetros :", best["params"])
    print("   • Métricas   :", best["metrics"])

    return (best["strategy"],
            mapper[best["strategy"]],
            best["params"],
            best["metrics"])

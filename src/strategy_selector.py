# src/strategy_selector.py
"""
Selector de estrategia basado en resultados de optimización y/o overrides por ENV.

Características:
- Busca primero archivos por timeframe (p.ej. results/rsi_optimization_15m.csv),
  y si no existen, usa los genéricos (sin sufijo).
- Ranking robusto: Sharpe → Total Return, penalizando drawdown extremo.
- Overrides por variables de entorno: FORCE_STRATEGY, RSI_PERIOD, SMA_PERIOD,
  RSI_BUY, RSI_SELL, etc.
- Fallback prudente si no hay CSVs.
"""

import os
import pandas as pd
from typing import Dict, Any, Tuple, Optional

# Mapea nombres a funciones reales de estrategia
from src.strategy import (
    moving_average_crossover,
    rsi_sma_strategy,
    macd_strategy,
)


def _convert(v):
    """Sanear tipos (np.int64 → int, etc.)."""
    try:
        import numpy as np
        if isinstance(v, (np.integer, np.floating)):
            return v.item()
    except Exception:
        pass
    return v


def _first_existing(paths):
    """Devuelve el primer path existente o None."""
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def _best_from_csv(path: str, strat: str, param_cols: list) -> Optional[Dict[str, Any]]:
    """Lee el CSV y devuelve un dict con strategy/params/metrics del mejor set."""
    if not path or not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df is None or df.empty:
        return None

    # Ranking: Sharpe → Total Return si existen; si no, primer registro
    sort_cols = [c for c in ["sharpe_ratio", "total_return"] if c in df.columns]
    if sort_cols:
        best = df.sort_values(sort_cols, ascending=[False] * len(sort_cols)).iloc[0]
    else:
        best = df.iloc[0]

    params = {}
    for k in param_cols:
        if k in df.columns:
            params[k] = _convert(best[k])
    metrics = {
        "total_return": float(best["total_return"]) if "total_return" in df.columns else 0.0,
        "sharpe_ratio": float(best["sharpe_ratio"]) if "sharpe_ratio" in df.columns else 0.0,
        "max_drawdown": float(best["max_drawdown"]) if "max_drawdown" in df.columns else 0.0,
    }
    return dict(strategy=strat, params=params, metrics=metrics)


def _score(metrics: Dict[str, float]) -> Tuple[float, float]:
    """
    Puntúa (para ordenar): (Sharpe, TR penalizado por DD extremo).
    max_drawdown se espera negativo (p.ej. -0.25 = -25%).
    """
    sr = float(metrics.get("sharpe_ratio", 0.0))
    tr = float(metrics.get("total_return", 0.0))
    mdd = float(metrics.get("max_drawdown", 0.0))
    penalty = -abs(mdd) if mdd < -0.25 else 0.0  # penaliza DD > 25%
    return sr, tr + penalty


def select_best_strategy(tf: str = "1h"):
    """
    Selecciona (nombre, función, params, metrics) de la mejor estrategia para el timeframe.
    Respeta overrides por ENV.
    """
    suf = f"_{tf}" if tf and tf != "1h" else ""

    # Localiza CSVs por prioridad: con sufijo → sin sufijo
    rsi_path = _first_existing([f"results/rsi_optimization{suf}.csv", "results/rsi_optimization.csv"])
    macd_path = _first_existing([f"results/macd_optimization{suf}.csv", "results/macd_optimization.csv"])
    sma_path = _first_existing([f"results/sma_optimization{suf}.csv", "results/sma_optimization.csv"])

    candidates = []

    # RSI+SMA
    rsi_best = _best_from_csv(
        rsi_path,
        "rsi_sma",
        ["rsi_period", "sma_period", "rsi_buy", "rsi_sell"],
    )
    if rsi_best:
        candidates.append(rsi_best)

    # MACD
    macd_best = _best_from_csv(
        macd_path,
        "macd",
        ["short_ema", "long_ema", "signal_ema"],
    )
    if macd_best:
        candidates.append(macd_best)

    # Medias móviles
    ma_best = _best_from_csv(
        sma_path,
        "moving_average",
        ["short_window", "long_window"],
    )
    if ma_best:
        candidates.append(ma_best)

    # Fallback prudente si no hay CSVs
    if not candidates:
        candidates = [
            dict(
                strategy="rsi_sma",
                params=dict(rsi_period=14, sma_period=100, rsi_buy=32, rsi_sell=62),
                metrics=dict(total_return=0.0, sharpe_ratio=0.0, max_drawdown=0.0),
            )
        ]

    # Ordena por score (Sharpe → TR penalizado)
    candidates.sort(key=lambda x: _score(x["metrics"]), reverse=True)
    best = candidates[0]

    # Overrides por ENV
    force = os.getenv("FORCE_STRATEGY", "").strip().lower()
    if force in {"rsi_sma", "macd", "moving_average"}:
        forced = [c for c in candidates if c["strategy"] == force]
        if forced:
            best = forced[0]

    # Overrides de parámetros (si aplica a la estrategia)
    # RSI_SMA
    if best["strategy"] == "rsi_sma":
        for key in ("rsi_period", "sma_period", "rsi_buy", "rsi_sell"):
            envk = os.getenv(key.upper())
            if envk is not None:
                best["params"][key] = int(envk)
    # MACD
    if best["strategy"] == "macd":
        for key in ("short_ema", "long_ema", "signal_ema"):
            envk = os.getenv(key.upper())
            if envk is not None:
                best["params"][key] = int(envk)
    # SMA crossover
    if best["strategy"] == "moving_average":
        for key in ("short_window", "long_window"):
            envk = os.getenv(key.upper())
            if envk is not None:
                best["params"][key] = int(envk)

    mapper = dict(
        moving_average=moving_average_crossover,
        rsi_sma=rsi_sma_strategy,
        macd=macd_strategy,
    )

    print("\n🏆 Estrategia seleccionada")
    print("   • Nombre     :", best["strategy"])
    print("   • Parámetros :", best["params"])
    print("   • Métricas   :", best["metrics"])
    print("   • Fuente     : selector basado en CSVs / ENV ✅")

    return best["strategy"], mapper[best["strategy"]], best["params"], best["metrics"]

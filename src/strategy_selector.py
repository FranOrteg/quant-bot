# src/strategy_selector.py

import os
import json
import math
import pandas as pd

# Importa las funciones de estrategia reales
from src.strategy import rsi_sma_strategy, macd_strategy, moving_average_crossover

# ---------- Utilidades ----------
def _exists(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _normalize_series(s: pd.Series):
    """Escala 0..1; si es cte, devuelve 0.5 para todo."""
    if s.empty:
        return s
    lo, hi = s.min(), s.max()
    if not math.isfinite(lo) or not math.isfinite(hi):
        return pd.Series([0.5]*len(s), index=s.index)
    if hi - lo == 0:
        return pd.Series([0.5]*len(s), index=s.index)
    return (s - lo) / (hi - lo)

def _robust_score(df: pd.DataFrame) -> pd.Series:
    """
    Score robusto combinando métricas:
      + total_return (más es mejor)
      + sharpe_ratio (más es mejor)
      - |max_drawdown| (menos drawdown en valor absoluto es mejor)
    Si hay 'total_trades', filtra >= 10 por defecto y premia ligeramente más trades.
    """
    if df.empty:
        return pd.Series(dtype=float)

    # Normalizaciones
    ret = _normalize_series(df["total_return"].astype(float)) if "total_return" in df.columns else pd.Series([0.5]*len(df), index=df.index)
    shp = _normalize_series(df["sharpe_ratio"].astype(float)) if "sharpe_ratio" in df.columns else pd.Series([0.5]*len(df), index=df.index)

    # max_drawdown suele ser negativo; usamos magnitud absoluta para penalizar
    if "max_drawdown" in df.columns:
        dd_abs = df["max_drawdown"].astype(float).abs()
        dd = 1 - _normalize_series(dd_abs)  # menos DD_abs → valor más cercano a 1
    else:
        dd = pd.Series([0.5]*len(df), index=df.index)

    base = 0.5 * ret + 0.4 * shp + 0.1 * dd  # pesos razonables por defecto

    # Pequeña prima por más operaciones si existe la columna
    if "total_trades" in df.columns:
        trades = df["total_trades"].astype(float)
        # Filtro mínimo de trades (evitar sobreajuste con 1-2 trades)
        valid = trades >= 10
        base = base.where(valid, other=base * 0.5)  # penaliza los muy escasos
        base += 0.05 * _normalize_series(trades.clip(upper=200.0))  # prima suave

    return base

def _best_from_csv(path: str, param_cols):
    if not _exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None

    # Asegura columnas clave si faltan
    for col in ["total_return", "sharpe_ratio", "max_drawdown"]:
        if col not in df.columns:
            df[col] = 0.0

    df["__score__"] = _robust_score(df)
    best = df.sort_values("__score__", ascending=False).iloc[0]

    params = {}
    for k in param_cols:
        if k in df.columns:
            # convertir a int si aplica
            v = best[k]
            try:
                v2 = int(v)
            except Exception:
                try:
                    v2 = float(v)
                except Exception:
                    v2 = v
            params[k] = v2

    metrics = dict(
        total_return=_safe_float(best.get("total_return", 0.0)),
        sharpe_ratio=_safe_float(best.get("sharpe_ratio", 0.0)),
        max_drawdown=_safe_float(best.get("max_drawdown", 0.0)),
        score=_safe_float(best.get("__score__", 0.0)),
        total_trades=int(best.get("total_trades", 0)) if "total_trades" in df.columns else None,
    )

    return dict(params=params, metrics=metrics, source=os.path.basename(path))

# ---------- Selector principal ----------
def select_best_strategy(tf: str = "1h"):
    """
    Selecciona la mejor estrategia en función del timeframe:
      1) Intenta usar CSVs de optimización del timeframe (p.ej. _15m).
      2) Si faltan, cae a CSVs genéricos sin sufijo.
      3) Si no hay nada, usa un set por defecto razonable.
    Permite override con:
      - STRATEGY_OVERRIDE=rsi_sma|macd|moving_average
      - PARAMS_OVERRIDE='{"rsi_period":14,"sma_period":20,"rsi_buy":40,"rsi_sell":60}'
    """
    suf = f"_{tf}" if tf else ""
    # Rutas por estrategia
    PATHS = [
        ("rsi_sma",    [f"results/rsi_optimization{suf}.csv", "results/rsi_optimization.csv"],
                       ["rsi_period", "sma_period", "rsi_buy", "rsi_sell"]),
        ("macd",       [f"results/macd_optimization{suf}.csv", "results/macd_optimization.csv"],
                       ["short_ema", "long_ema", "signal_ema"]),
        ("moving_average", [f"results/sma_optimization{suf}.csv", "results/sma_optimization.csv"],
                       ["short_window", "long_window"]),
    ]

    candidates = []
    for strat_name, candidates_paths, param_cols in PATHS:
        entry = None
        for p in candidates_paths:
            entry = _best_from_csv(p, param_cols)
            if entry:
                entry["strategy"] = strat_name
                candidates.append(entry)
                break

    # Override por ENV
    env_strat = os.getenv("STRATEGY_OVERRIDE", "").strip()
    env_params = os.getenv("PARAMS_OVERRIDE", "").strip()

    if env_strat:
        # Si hay override de estrategia, obliga a usarla. Si hay params también, los aplica.
        forced = dict(strategy=env_strat, params={}, metrics=dict(), source="ENV_OVERRIDE")
        if env_params:
            try:
                forced["params"] = json.loads(env_params)
            except Exception:
                print("⚠️ PARAMS_OVERRIDE no es JSON válido; se ignora.")
        candidates = [forced]  # prioridad absoluta

    # Si no hay candidatos de CSV ni override, define defaults razonables por TF
    if not candidates:
        if tf == "15m":
            candidates = [dict(
                strategy="rsi_sma",
                params=dict(rsi_period=10, sma_period=20, rsi_buy=40, rsi_sell=60),
                metrics=dict(total_return=0.0, sharpe_ratio=0.0, max_drawdown=0.0, score=0.0),
                source="FALLBACK_15m"
            )]
        else:
            candidates = [dict(
                strategy="rsi_sma",
                params=dict(rsi_period=14, sma_period=50, rsi_buy=30, rsi_sell=70),
                metrics=dict(total_return=0.0, sharpe_ratio=0.0, max_drawdown=0.0, score=0.0),
                source="FALLBACK_GENERIC"
            )]

    # Elige el mejor por score si existe; si no, primero de la lista
    best = None
    scored = [c for c in candidates if "metrics" in c and isinstance(c["metrics"], dict) and "score" in c["metrics"]]
    if scored:
        best = sorted(scored, key=lambda x: _safe_float(x["metrics"]["score"], 0.0), reverse=True)[0]
    else:
        best = candidates[0]

    # Mapa estrategia → función
    mapper = dict(
        rsi_sma=rsi_sma_strategy,
        macd=macd_strategy,
        moving_average=moving_average_crossover,
    )

    strat = best["strategy"]
    func = mapper[strat]
    params = best.get("params", {})
    metrics = best.get("metrics", {})
    source = best.get("source", "UNKNOWN")

    print("\n🏆 Estrategia seleccionada")
    print(f"   • Nombre     : {strat}")
    print(f"   • Parámetros : {params}")
    print(f"   • Métricas   : {metrics}")
    print(f"   • Fuente     : {source} ✅")

    return strat, func, params, metrics

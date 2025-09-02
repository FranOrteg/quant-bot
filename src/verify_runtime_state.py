# -*- coding: utf-8 -*-
import os, json, textwrap
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timezone
from src.binance_api import get_historical_data

load_dotenv()

SYMBOL    = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME = os.getenv("TRADING_TIMEFRAME", "15m")
DATA_CSV  = f"data/{SYMBOL}_{TIMEFRAME}.csv"
OPT_CSV   = f"results/rsi_optimization_{TIMEFRAME}.csv"
ACTIVE_JSON = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"

# Quality gate (mismos ENV que usa el reoptimizer)
MIN_RET_PCT = float(os.getenv("REOPT_MIN_RETURN_PCT", "0"))   # p.ej. 0
MIN_SHARPE  = float(os.getenv("REOPT_MIN_SHARPE", "0"))       # p.ej. 0
MAX_DD_PCT  = float(os.getenv("REOPT_MAX_DD_PCT", "20"))      # p.ej. 20  → CSV tiene DD NEGATIVO

# Param extra de la estrategia viva
LOOKBACK_BARS = int(os.getenv("RSI_LOOKBACK_BARS", "8"))

def _read_active():
    if not os.path.exists(ACTIVE_JSON):
        return None
    with open(ACTIVE_JSON, "r") as f:
        return json.load(f)

def _print_active(active):
    best = active.get("best", {})
    print("\n🏆 Estrategia seleccionada")
    print(f"   • Nombre     : {best.get('strategy','?')}")
    print(f"   • Parámetros : {best.get('params',{})}")
    print(f"   • Métricas   : {best.get('metrics',{})}")
    print(f"   • Fuente     : ACTIVE_PARAMS_JSON ✅")

def _load_prices():
    # Preferimos el CSV si existe; si no, tiramos del fetch directo (sincrónico).
    if os.path.exists(DATA_CSV):
        df = pd.read_csv(DATA_CSV)
        # saneo mínimo en memoria
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        for c in ["open","high","low","close","volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)
        # si es demasiado corto o viejo, hago fallback a fetch
        if len(df) >= 200:
            return df
        print("ℹ️ CSV muy corto; se traerán velas recientes…")
    # fallback
    print("↓ Descargando OHLCV de respaldo (no escribe a disco)…")
    return get_historical_data(SYMBOL, TIMEFRAME, 1200)

def _recalc_last_signal(df, params):
    from src.strategy.rsi_sma import rsi_sma_strategy
    # añadimos lookback_bars si la estrategia lo soporta (lo ignora si no)
    pp = dict(params)
    pp.setdefault("lookback_bars", LOOKBACK_BARS)
    # en verify, asumimos flat para señal “de esta vela”
    out = rsi_sma_strategy(df.copy(), in_position=False, **pp)
    last = out.iloc[-1]
    # preparar resumen seguro (puede que no existan todas las cols)
    close = float(last.get("close", float("nan")))
    sma   = float(last.get("sma", float("nan")))
    rsi   = float(last.get("rsi", float("nan")))
    pos   = int(last.get("position", 0))
    reason= str(last.get("reason", ""))
    print("\n📈 3) Últimos valores recalculados (con la MISMA estrategia viva):")
    print(f"   • close: {close:,.2f}  SMA({params.get('sma_period')}): {sma:,.2f}  RSI({params.get('rsi_period')}): {rsi:.2f}")
    print(f"   • Señal calculada (esta vela): {pos}   Motivo: {reason}")

def _csv_best(abs_or_gate="abs"):
    if not os.path.exists(OPT_CSV):
        return None, "CSV no encontrado"
    df = pd.read_csv(OPT_CSV)
    if df.empty:
        return None, "CSV vacío"

    # coerción
    for c in ("total_return", "sharpe_ratio", "max_drawdown"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["total_return"])
    if df.empty:
        return None, "CSV sin total_return válido"

    if abs_or_gate == "gate":
        passed = df[
            (df["total_return"] >= MIN_RET_PCT) &
            (df["sharpe_ratio"] >= MIN_SHARPE) &
            (df["max_drawdown"] >= -abs(MAX_DD_PCT))
        ]
        if passed.empty:
            return None, f"ninguna fila pasa gate(min_ret={MIN_RET_PCT}%, min_sharpe={MIN_SHARPE}, maxDD=-{abs(MAX_DD_PCT)}%)"
        df = passed

    row = df.sort_values("total_return", ascending=False).iloc[0]
    params = dict(
        rsi_period = int(row["rsi_period"]),
        sma_period = int(row["sma_period"]),
        rsi_buy    = int(row["rsi_buy"]),
        rsi_sell   = int(row["rsi_sell"]),
    )
    metrics = dict(
        total_return = float(row.get("total_return", 0.0)),
        sharpe_ratio = float(row.get("sharpe_ratio", 0.0)),
        max_drawdown = float(row.get("max_drawdown", 0.0)),
    )
    return {"params": params, "metrics": metrics}, "ok"

def _params_eq(a,b):
    keys = ["rsi_period","sma_period","rsi_buy","rsi_sell"]
    return all(a.get(k)==b.get(k) for k in keys)

def main():
    print("\n🔎 1) ¿Qué parámetros está usando AHORA el bot?")
    active = _read_active()
    if not active:
        print(f"❌ No existe {ACTIVE_JSON}. ¿Está corriendo el reoptimizer?")
        return
    best = active["best"]
    _print_active(active)

    print("\n🧪 2) Validación de datos de precio")
    df = _load_prices()
    ts_min, ts_max = df["timestamp"].iloc[0], df["timestamp"].iloc[-1]
    # Heurística básica de gaps
    gaps = ""
    try:
        spacing = pd.Series(df["timestamp"]).diff().dropna().value_counts().head(3)
        if len(spacing) > 1:
            gaps = f"⚠️ Intervalos múltiples detectados (posibles huecos). Top diffs:\n{spacing}"
    except Exception:
        pass
    print(f"   • Filas: {len(df)}   rango: {ts_min} → {ts_max}")
    if gaps: print(textwrap.indent(gaps, "   "))

    # 3) Recalcular señal con ESTRATEGIA VIVA
    _recalc_last_signal(df, best["params"])

    # 4) CSV – top absoluto y top que pasa gate
    print("\n🏁 4) Comparativa con CSV de optimización:")
    abs_top, abs_msg = _csv_best("abs")
    gate_top, gate_msg = _csv_best("gate")

    if abs_top:
        print(f"   • Top ABS params : {abs_top['params']} | métricas: {abs_top['metrics']}")
    else:
        print(f"   • Top ABS        : {abs_msg}")

    if gate_top:
        print(f"   • Top GATE params: {gate_top['params']} | métricas: {gate_top['metrics']}")
    else:
        print(f"   • Top GATE       : {gate_msg}")

    # 5) Estado de sincronización
    print("\n🔄 5) ¿Está sincronizado lo que corre el bot?")
    active_params = best["params"]
    if gate_top and _params_eq(active_params, gate_top["params"]):
        print("   ✅ Activo == Top que pasa GATE → coherente con el reoptimizer.")
    elif abs_top and _params_eq(active_params, abs_top["params"]):
        print("   ✅ Activo == Top ABS del CSV → coherente.")
    else:
        print("   ⚠️ Activo NO coincide ni con Top ABS ni con Top GATE.")
        print("      → Ejecuta manualmente la optimización o revisa el gate/envs.")
        print(f"      ACTIVE: {active_params}")

    print("\nℹ️ Nota: la estrategia viva puede usar 'lookback_bars' "
          f"(ahora {LOOKBACK_BARS}) que no está en el CSV si aún no lo añadiste al optimizador.")
    print()

if __name__ == "__main__":
    main()

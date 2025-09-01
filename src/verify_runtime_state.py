# src/verify_runtime_state.py
import os
import re
import json
import math
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# 1) Importar el selector real del proyecto
from src.strategy_selector import select_best_strategy

DATA_PATH = Path("data/BTCUSDC_15m.csv")
LOG_PATH  = Path("logs/live_trader.log")
OPT_PATH  = Path("results/rsi_optimization_15m.csv")

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return np.nan

def load_and_validate_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}. Asegúrate de que el bot esté generándolo.")

    # Cargar crudo (sin parseo todavía) para detectar contaminaciones
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()

    bad_lines = []
    clean_lines = []
    header_seen = False
    for i, ln in enumerate(lines):
        if not header_seen:
            clean_lines.append(ln)
            header_seen = True
            continue

        # Heurística: una línea válida debe tener 6 columnas separadas por coma
        # y las columnas 2..6 deben ser numéricas (open,high,low,close,volume)
        parts = ln.split(",")
        if len(parts) != 6:
            bad_lines.append((i+1, "num_cols", ln))
            continue

        ts, o, h, l, c, v = parts
        # Si el volumen tiene texto del log pegado, no será numérico
        if any((_safe_float(x) is np.nan) for x in (o, h, l, c, v)):
            bad_lines.append((i+1, "non_numeric", ln))
            continue

        clean_lines.append(ln)

    # Reporte de líneas malas
    if bad_lines:
        print("⚠️ Se detectaron líneas corruptas en el CSV (se ignorarán en la validación):")
        for n, reason, ln in bad_lines[:5]:
            print(f"   • Línea {n} [{reason}]: {ln[:120]}{'...' if len(ln)>120 else ''}")
        if len(bad_lines) > 5:
            print(f"   • y {len(bad_lines)-5} más...")

    # Reconstruir CSV solo con líneas válidas para la validación en memoria
    tmp = "\n".join(clean_lines)
    from io import StringIO
    df = pd.read_csv(StringIO(tmp))

    # Parseo de timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    # Coherencia temporal
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    # Eliminar duplicados de timestamp (dejar el último)
    before = len(df)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    after = len(df)
    if after < before:
        print(f"ℹ️ Eliminados {before-after} duplicados de timestamp (en validación).")

    # Asegurar tipos numéricos
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)

    return df

def compute_indicators_and_signal(df: pd.DataFrame, rsi_period: int, sma_period: int,
                                  rsi_buy: int, rsi_sell: int) -> pd.DataFrame:
    # SMA
    df["sma"] = df["close"].rolling(sma_period, min_periods=sma_period).mean()

    # RSI
    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_gain = pd.Series(gain, index=df.index).rolling(rsi_period, min_periods=rsi_period).mean()
    roll_loss = pd.Series(loss, index=df.index).rolling(rsi_period, min_periods=rsi_period).mean()
    rs = roll_gain / roll_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi"] = df["rsi"].bfill()  # suavizar arranque

    # Señal estilo rsi_sma (long-only): 
    # entrada si precio > SMA y RSI < rsi_buy; salida si RSI > rsi_sell
    # (ajústalo a tu lógica exacta si difiere)
    df["position"] = 0
    in_pos = False
    for i in range(len(df)):
        price = df.at[i, "close"]
        sma   = df.at[i, "sma"]
        rsi   = df.at[i, "rsi"]
        if not np.isnan(sma):
            if not in_pos and price > sma and rsi <= rsi_buy:
                df.at[i, "position"] = 1
                in_pos = True
            elif in_pos and rsi >= rsi_sell:
                df.at[i, "position"] = -1
                in_pos = False
        # Si no hay señal nueva, mantener 0 (el bot gestiona el estado con su variable `position`)
    return df

def tail_log_last_signal(log_path: Path) -> dict | None:
    if not log_path.exists():
        return None
    tail = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
    # Buscar la última línea con "Precio: ... | Señal: ..."
    pat = re.compile(r"Precio:\s*([0-9.]+)\s*\|\s*Señal:\s*(-?1|0)")
    last = None
    for ln in reversed(tail):
        m = pat.search(ln)
        if m:
            price = float(m.group(1))
            sig = int(m.group(2))
            last = {"price": price, "signal": sig, "raw": ln}
            break
    return last

def pick_best_from_optimization(opt_path: Path):
    if not opt_path.exists():
        return None
    df = pd.read_csv(opt_path)
    need = {"total_return", "sharpe_ratio", "max_drawdown", "rsi_period", "sma_period", "rsi_buy", "rsi_sell"}
    if not need.issubset(df.columns):
        return None

    # Score robusto: prioriza retorno pero penaliza DD profundo y Sharpe bajo
    # normalización simple para ranking
    d = df.copy()
    d = d.dropna(subset=["total_return", "sharpe_ratio", "max_drawdown"])
    if d.empty:
        return None

    # Evitar divisiones por cero / escalas raras
    d["ret_z"]   = (d["total_return"] - d["total_return"].mean()) / (d["total_return"].std(ddof=0) + 1e-9)
    d["sharpe_z"] = (d["sharpe_ratio"] - d["sharpe_ratio"].mean()) / (d["sharpe_ratio"].std(ddof=0) + 1e-9)
    # drawdown es negativo; más cercano a 0 es mejor → usar el negativo
    d["dd_z"] = - (d["max_drawdown"] - d["max_drawdown"].mean()) / (d["max_drawdown"].std(ddof=0) + 1e-9)

    # Ponderación
    d["score"] = 0.6 * d["ret_z"] + 0.3 * d["sharpe_z"] + 0.1 * d["dd_z"]
    best = d.sort_values("score", ascending=False).iloc[0]
    return {
        "params": {
            "rsi_period": int(best["rsi_period"]),
            "sma_period": int(best["sma_period"]),
            "rsi_buy": int(best["rsi_buy"]),
            "rsi_sell": int(best["rsi_sell"]),
        },
        "metrics": {
            "total_return": float(best["total_return"]),
            "sharpe_ratio": float(best["sharpe_ratio"]),
            "max_drawdown": float(best["max_drawdown"]),
            "score": float(best["score"]),
        }
    }

def main():
    print("\n🔎 1) ¿Qué parámetros está usando AHORA el bot segun el selector?")
    strat_name, strat_fn, params, metrics = select_best_strategy(tf="15m")
    print(f"   • Estrategia : {strat_name}")
    print(f"   • Params     : {params}")
    print(f"   • Métricas   : {metrics}")

    print("\n🧪 2) Validación del CSV en memoria (sin tocar el archivo):")
    df = load_and_validate_csv(DATA_PATH)
    print(f"   • Filas válidas: {len(df)}   rango: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")

    # Detectar gaps de 15m y timestamps no monotónicos
    diffs = df["timestamp"].diff().dropna().dt.total_seconds()
    bad_gap = diffs[(diffs != 900.0) & (diffs != 0.0)]  # 900s = 15m; 0 si hay duplicado (ya limpiado)
    if not bad_gap.empty:
        print(f"   • ⚠️ Gaps o irregularidades detectados en {len(bad_gap)} puntos (p.ej. velas faltantes).")

    # Recalcular indicadores y señal con los parámetros en uso
    df_ind = compute_indicators_and_signal(df.copy(), **params)
    last = df_ind.iloc[-1]
    print("\n📈 3) Últimos valores recalculados:")
    print(f"   • close: {last.close:.2f}  SMA({params['sma_period']}): {last.sma:.2f}  RSI({params['rsi_period']}): {last.rsi:.2f}")
    print(f"   • Señal calculada (esta vela): {int(last.position)}")

    # Comparar con lo que logueó el bot
    log_last = tail_log_last_signal(LOG_PATH)
    if log_last:
        print("\n🪵 4) Última señal según logs:")
        print(f"   • Log: {log_last['raw']}")
        # Nota: el bot mantiene un estado de posición; si en la vela anterior se entró/salió,
        # puede que esta vela registre 0 aunque nuestra lógica base genere 1/-1 solo en el cruce.
        # Aun así, suele coincidir el *timing* de las señales.
        print(f"\n🔁 5) Comparativa rápida:")
        print(f"   • Señal log    : {log_last['signal']}")
        print(f"   • Señal calc   : {int(last.position)}")
        if int(last.position) != log_last["signal"]:
            print("   • ⚠️ Diferencia detectada: revisa la lógica exacta de tu rsi_sma en src/strategy/rsi_sma.py")
        else:
            print("   • ✅ Coinciden.")
    else:
        print("\n🪵 4) No encontré una línea de señal en logs recientes. Revisa logs/live_trader.log")

    # (Opcional) mostrar el “mejor” set de results/rsi_optimization_15m.csv si existe
    if OPT_PATH.exists():
        best_opt = pick_best_from_optimization(OPT_PATH)
        if best_opt:
            print("\n🏁 6) Mejor set según results/rsi_optimization_15m.csv (score robusto):")
            print(f"   • Params  : {best_opt['params']}")
            print(f"   • Métricas: {best_opt['metrics']}")
            # ¿Coincide con los que usa el bot?
            same = all(int(params[k]) == int(best_opt["params"][k]) for k in ["rsi_period","sma_period","rsi_buy","rsi_sell"])
            print(f"   • ¿Coinciden con los del bot?: {'✅ Sí' if same else '❌ No'}")
        else:
            print("\nℹ️ 6) No pude interpretar results/rsi_optimization_15m.csv (faltan columnas o está vacío).")
    else:
        print("\nℹ️ 6) No hay results/rsi_optimization_15m.csv, el selector no puede apoyarse en ese histórico.")

    # Sugerencia de saneo si hubo líneas malas
    print("\n🧹 Sugerencia de saneo si detectaste líneas corruptas en el CSV:")
    print(f"""   • Haz un backup y reescríbelo limpio con:
       python - <<'PY'
import pandas as pd
df = pd.read_csv("{DATA_PATH.as_posix()}")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
df = df.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
for col in ["open","high","low","close","volume"]: df[col] = pd.to_numeric(df[col], errors="coerce")
df = df.dropna(subset=["open","high","low","close","volume"]).reset_index(drop=True)
df.to_csv("{DATA_PATH.as_posix()}", index=False)
print("CSV saneado y reescrito")
PY
    """)

if __name__ == "__main__":
    main()

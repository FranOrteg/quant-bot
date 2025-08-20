# src/fix_data_gaps.py
import os
import argparse
import pandas as pd
from src.binance_api import get_historical_data

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol",    default="BTCUSDC")
    p.add_argument("--timeframe", default="15m")
    p.add_argument("--limit",     type=int, default=1500, help="velas a regenerar")
    args = p.parse_args()

    path = f"data/{args.symbol}_{args.timeframe}.csv"
    os.makedirs("data", exist_ok=True)

    # 1) Descargar bloque reciente desde Binance
    fresh = get_historical_data(args.symbol, args.timeframe, args.limit)
    fresh["timestamp"] = pd.to_datetime(fresh["timestamp"], utc=True)

    # 2) Cargar csv existente (si existe)
    if os.path.exists(path):
        old = pd.read_csv(path)
        old["timestamp"] = pd.to_datetime(old["timestamp"], utc=True, errors="coerce")
        # 3) Concatenar y limpiar
        df = pd.concat([old, fresh], ignore_index=True)
    else:
        df = fresh.copy()

    # 4) Tipos y limpieza
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = (
        df.dropna(subset=["timestamp","open","high","low","close","volume"])
          .drop_duplicates(subset=["timestamp"], keep="last")
          .sort_values("timestamp")
          .reset_index(drop=True)
    )

    # 5) Persistir
    df.to_csv(path, index=False)
    print(f"✅ Dataset saneado/actualizado: {path}")
    print(f"   • filas: {len(df)}  rango: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")

if __name__ == "__main__":
    main()

# src/migrations/normalize_performance_logs.py
# -*- coding: utf-8 -*-
import os
import sys
import glob
import shutil
from datetime import datetime
import argparse
import pandas as pd
import numpy as np

DEFAULT_DIR = "logs"

def backup_file(path: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.bak.{ts}"
    shutil.copy2(path, dst)
    return dst

def to_float(x):
    try:
        if pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan

def normalize_performance_csv(path: str, quote_asset: str, dry_run: bool = False) -> dict:
    df = pd.read_csv(path)
    cols = list(df.columns)
    changed = False
    notes = []

    # Normaliza nombres por si vienen con mayúsculas/variantes (suaves)
    # (No renombramos, solo leemos con tolerancia)
    col_timestamp = "timestamp" if "timestamp" in cols else None
    col_action    = "action" if "action" in cols else None
    col_price     = "price" if "price" in cols else None
    col_btc       = "BTC" if "BTC" in cols else None
    col_equity    = "equity" if "equity" in cols else None

    # Si falta la columna del QUOTE_ASSET, la creamos
    if quote_asset not in cols:
        # Caso más común: ya existe USDT → copiamos valores
        if "USDT" in cols:
            df[quote_asset] = df["USDT"]
            notes.append(f"añadida {quote_asset} desde USDT")
        else:
            # Intentamos reconstruir cash = equity - BTC * price
            if col_equity and col_btc and col_price:
                cash = df[col_equity].astype(float) - df[col_btc].astype(float) * df[col_price].astype(float)
                df[quote_asset] = cash
                notes.append(f"añadida {quote_asset} reconstruida de equity - BTC*price")
            else:
                # si no podemos, dejamos NaN
                df[quote_asset] = np.nan
                notes.append(f"añadida {quote_asset} con NaN (sin USDT ni forma de reconstruir)")

        changed = True
        cols = list(df.columns)

    # Aseguramos compat antigua: si no hay USDT, lo creamos duplicando QUOTE_ASSET
    if "USDT" not in cols:
        df["USDT"] = df[quote_asset]
        notes.append("añadida USDT (compat) duplicando " + quote_asset)
        changed = True
        cols = list(df.columns)

    # Reorden de columnas recomendado
    # timestamp, action, price, <QUOTE_ASSET>, USDT, BTC, equity, (resto…)
    preferred = [
        "timestamp",
        "action",
        "price",
        quote_asset,
        "USDT",
        "BTC",
        "equity",
    ]
    ordered = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    if ordered != list(df.columns):
        df = df[ordered]
        changed = True
        notes.append("reorden de columnas")

    # Guardado
    backup_path = None
    if changed and not dry_run:
        backup_path = backup_file(path)
        df.to_csv(path, index=False)

    return {
        "file": path,
        "changed": changed,
        "backup": backup_path,
        "notes": ", ".join(notes) if notes else "sin cambios",
        "columns": list(df.columns),
        "rows": len(df),
    }

def main():
    parser = argparse.ArgumentParser(description="Normaliza performance_log*.csv añadiendo la columna de QUOTE_ASSET.")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="Directorio de logs (por defecto: logs)")
    parser.add_argument("--quote", default=os.getenv("QUOTE_ASSET", "USDC"), help="Activo de caja (USDC/USDT/...). Por defecto env QUOTE_ASSET o USDC.")
    parser.add_argument("--dry-run", action="store_true", help="No escribe cambios; solo informa.")
    args = parser.parse_args()

    quote_asset = args.quote.upper()
    pattern = os.path.join(args.dir, "performance_log*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"⚠️ No se encontraron CSVs con patrón: {pattern}")
        sys.exit(0)

    print(f"🔎 QUOTE_ASSET objetivo: {quote_asset}")
    print(f"📂 Directorio: {args.dir}")
    print(f"🧪 Dry-run: {args.dry_run}")
    print("────────────────────────────────────────────────────────────")

    summary = []
    for path in files:
        try:
            res = normalize_performance_csv(path, quote_asset, dry_run=args.dry_run)
            summary.append(res)
            status = "✅ cambiado" if res["changed"] else "OK"
            extra  = f" | backup: {res['backup']}" if res["backup"] else ""
            print(f"{status} → {os.path.basename(path)} ({res['rows']} filas) | {res['notes']}{extra}")
        except Exception as e:
            print(f"❌ Error con {path}: {e}")

    print("────────────────────────────────────────────────────────────")
    print("Resumen:")
    for r in summary:
        print(f"- {os.path.basename(r['file'])}: {'cambios' if r['changed'] else 'sin cambios'} | cols={r['columns']}")

if __name__ == "__main__":
    main()

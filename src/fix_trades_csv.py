# src/fix_trades_csv.py

import pandas as pd
import json
import os

INPUT_PATH = "logs/trades.csv"
BACKUP_PATH = "logs/trades_backup.csv"

def clean_params(p):
    try:
        # Intenta cargar el string como JSON
        return json.dumps(json.loads(p.replace("'", '"')))
    except Exception:
        return "{}"  # Vacío si no se puede parsear

def main():
    if not os.path.exists(INPUT_PATH):
        print("❌ No se encontró logs/trades.csv")
        return

    df = pd.read_csv(INPUT_PATH)

    print(f"🔍 Corrigiendo {len(df)} entradas...")

    df["params"] = df["params"].apply(clean_params)

    # Hacemos backup antes de sobrescribir
    df.to_csv(BACKUP_PATH, index=False)
    df.to_csv(INPUT_PATH, index=False)

    print(f"✅ Archivo limpio guardado en {INPUT_PATH}")
    print(f"🛡️  Backup guardado en {BACKUP_PATH}")

if __name__ == "__main__":
    main()

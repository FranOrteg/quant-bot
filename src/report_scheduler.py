# src/report_scheduler.py

import os
import time
import hashlib
from src.generate_summary_report import generate_summary_report

TRADES_PATH = "logs/trades.csv"
CHECK_INTERVAL = 300  # cada 5 minutos (300 segundos)

def file_hash(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def main():
    print("📅 Iniciando monitor de generación de informes...")
    last_hash = file_hash(TRADES_PATH)

    while True:
        time.sleep(CHECK_INTERVAL)
        current_hash = file_hash(TRADES_PATH)

        if current_hash and current_hash != last_hash:
            print("📈 Cambios detectados en trades.csv. Generando nuevo resumen...")
            try:
                generate_summary_report()
                print("✅ Resumen actualizado.")
            except Exception as e:
                print(f"❌ Error al generar el resumen: {e}")
            last_hash = current_hash
        else:
            print("🕒 Sin cambios detectados. Esperando...")

if __name__ == "__main__":
    main()

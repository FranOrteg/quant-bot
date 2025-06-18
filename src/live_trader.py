# src/live_trader.py

import time
from binance.client import Client
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime, timezone
from src.strategy import moving_average_crossover
from src.paper_trading import buy, sell, get_price
import logging

load_dotenv()

symbol = 'BTCUSDT'
interval = 60 * 5  # cada 5 minutos (recomendado)
history = []

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/trading_bot.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

# Simula historial de precios
def fetch_historical_prices():
    global history
    now = datetime.now(timezone.utc)
    price = get_price()
    history.append({'timestamp': now, 'close': price})
    
    # Guardar cada punto nuevo en CSV
    save_to_csv({'timestamp': now.isoformat(), 'close': price})

    df = pd.DataFrame(history)
    df = moving_average_crossover(df)
    return df

# Guardar historico en un CSV
def save_to_csv(row, filename='data/BTCUSDT.csv'):
    os.makedirs('data', exist_ok=True)
    file_exists = os.path.isfile(filename)
    
    df_row = pd.DataFrame([row])
    df_row.to_csv(filename, mode='a', index=False, header=not file_exists)


def run_bot():
    position = 0  # 0 = fuera, 1 = comprado

    while True:
        df = fetch_historical_prices()
        last_row = df.iloc[-1]

        logging.info(f"Precio actual: {last_row['close']}  | SMA20: {last_row['SMA20']} | SMA50: {last_row['SMA50']}")

        if last_row['position'] == 1 and position == 0:
            logging.info("🟢 Señal de COMPRA detectada")
            buy(symbol)
            position = 1

        elif last_row['position'] == -1 and position == 1:
            logging.info("🔴 Señal de VENTA detectada")
            sell(symbol)
            position = 0
        time.sleep(interval)
        

if __name__ == "__main__":
    run_bot()

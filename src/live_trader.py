# src/live_trader.py

import time
from binance.client import Client
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime
from src.strategy import moving_average_crossover
from src.paper_trading import buy, sell, get_price

load_dotenv()

symbol = 'BTCUSDT'
interval = 60 * 5  # cada 5 minutos (recomendado)
history = []

# Simula historial de precios
def fetch_historical_prices():
    global history
    now = datetime.now(datetime.UTC)
    price = get_price()
    history.append({'timestamp': now, 'close': price})
    df = pd.DataFrame(history)
    df = moving_average_crossover(df)
    return df

def run_bot():
    position = 0  # 0 = fuera, 1 = comprado

    while True:
        df = fetch_historical_prices()
        last_row = df.iloc[-1]

        print(f"\n📈 Precio actual: {last_row['close']}  | SMA20: {last_row['SMA20']} | SMA50: {last_row['SMA50']}")
        
        if last_row['position'] == 1 and position == 0:
            buy()
            position = 1
        elif last_row['position'] == -1 and position == 1:
            sell()
            position = 0
        else:
            print("🟡 Sin acción. Esperando próxima vela...")

        time.sleep(interval)

if __name__ == "__main__":
    run_bot()

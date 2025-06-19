# src/live_trader.py

import time
from binance.client import Client
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime, timezone
from src.paper_trading import buy, sell, get_price
from src.strategy_selector import select_best_strategy
from src.strategy import moving_average_crossover, rsi_sma_strategy, macd_strategy
import logging

load_dotenv()

symbol = 'BTCUSDT'
interval = 60 * 5  # cada 5 minutos
history = []

# 🧠 Cargamos la mejor estrategia
strategy_name, strategy_func, params, _ = select_best_strategy()

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/live_trader.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

def fetch_historical_prices():
    global history
    now = datetime.now(timezone.utc)
    price = get_price()
    history.append({'timestamp': now, 'close': price})

    save_to_csv({'timestamp': now.isoformat(), 'close': price})

    df = pd.DataFrame(history)
    df = strategy_func(df, **params)
    return df

def save_to_csv(row, filename='data/BTCUSDT.csv'):
    os.makedirs('data', exist_ok=True)
    file_exists = os.path.isfile(filename)
    pd.DataFrame([row]).to_csv(filename, mode='a', index=False, header=not file_exists)

def run_bot():
    position = 0
    logging.info(f"🧠 Iniciando bot con estrategia: {strategy_name} | Parámetros: {params}")
    
    while True:
        df = fetch_historical_prices()
        if df.empty or 'position' not in df.columns:
            logging.warning("⚠️ Datos insuficientes para generar señal")
            time.sleep(interval)
            continue

        last_row = df.iloc[-1]

        logging.info(f"Precio: {last_row['close']} | Señal: {last_row['position']}")

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

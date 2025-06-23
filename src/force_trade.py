# src/force_trade.py
import sys
import os
import json
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TRADES_PATH = 'logs/trades.csv'


def log_operation(symbol, action, price, strategy_name, params):
    os.makedirs('logs', exist_ok=True)
    file_exists = os.path.isfile(TRADES_PATH)
    trade = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "strategy_name": strategy_name,
        "params": json.dumps(params)
    }
    pd.DataFrame([trade]).to_csv(TRADES_PATH, mode='a', index=False, header=not file_exists)


def main():
    if len(sys.argv) != 3:
        print("❌ Uso incorrecto. Formato: python3 -m src.force_trade [buy|sell] [precio]")
        sys.exit(1)

    action = sys.argv[1].upper()
    if action not in ['BUY', 'SELL']:
        print("❌ Acción inválida. Usa 'buy' o 'sell'")
        sys.exit(1)

    try:
        price = float(sys.argv[2])
    except ValueError:
        print("❌ El precio debe ser un número válido")
        sys.exit(1)

    # ⚙️ Aquí puedes modificar si cambias de estrategia
    symbol = "BTCUSDT"
    strategy_name = "rsi_sma"
    params = {"rsi_period": 14, "sma_period": 10, "rsi_buy": 30, "rsi_sell": 70}

    log_operation(symbol, action, price, strategy_name, params)
    print(f"✅ Señal {action} forzada insertada con precio {price}")


if __name__ == "__main__":
    main()

# utils.py
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TRADES_FILE = 'logs/trades.csv'
PERFORMANCE_FILE = 'logs/performance_log.csv'

def log_operation(symbol, action, price, strategy_name, params, filename=TRADES_FILE):
    os.makedirs('logs', exist_ok=True)
    file_exists = os.path.isfile(filename)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "strategy": strategy_name,
        "params": json.dumps(convert_params(params))
    }

    pd.DataFrame([data]).to_csv(filename, mode='a', index=False, header=not file_exists)

def log_performance(action, price, balance):
    os.makedirs('logs', exist_ok=True)
    file_exists = os.path.isfile(PERFORMANCE_FILE)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "price": price,
        "USDT": balance.get("USDT", 0.0),
        "BTC": balance.get("BTC", 0.0),
        "equity": balance.get("USDT", 0.0) + balance.get("BTC", 0.0) * price
    }

    pd.DataFrame([data]).to_csv(PERFORMANCE_FILE, mode='a', index=False, header=not file_exists)

def convert_params(params):
    def sanitize(v):
        if isinstance(v, (int, float, str)):
            return v
        if isinstance(v, (np.integer, np.floating)):
            return v.item()
        return str(v)

    return {k: sanitize(v) for k, v in params.items()}


# utils.py
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from math import floor

TRADES_FILE = 'logs/trades.csv'
PERFORMANCE_FILE = 'logs/performance_log.csv'

def log_operation(symbol, action, price, strategy_name, params, filename=None):
    os.makedirs('logs', exist_ok=True)
    if filename is None:
        filename = TRADES_FILE  # default: logs/trades.csv

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

def log_performance(action, price, balance, filename=None):
    os.makedirs('logs', exist_ok=True)
    if filename is None:
        filename = PERFORMANCE_FILE  # default: logs/performance_log.csv

    file_exists = os.path.isfile(filename)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "price": price,
        "USDT": balance.get("USDT", 0.0),
        "BTC": balance.get("BTC", 0.0),
        "equity": balance.get("USDT", 0.0) + balance.get("BTC", 0.0) * price
    }

    pd.DataFrame([data]).to_csv(filename, mode='a', index=False, header=not file_exists)


def convert_params(params):
    def sanitize(v):
        if isinstance(v, (int, float, str)):
            return v
        if isinstance(v, (np.integer, np.floating)):
            return v.item()
        return str(v)

    return {k: sanitize(v) for k, v in params.items()}


def prepare_quantity(free_btc: float, symbol_info: dict) -> float:
    lot_filter   = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size    = Decimal(lot_filter["stepSize"])
    min_qty      = Decimal(lot_filter["minQty"])

    qty_decimal  = Decimal(str(free_btc)).quantize(step_size, rounding=ROUND_DOWN)
    # Truncar al múltiplo exacto de stepSize
    steps        = (qty_decimal / step_size).to_integral_value(rounding=ROUND_DOWN)
    qty_decimal  = steps * step_size

    if qty_decimal < min_qty:
        return 0.0     # insuficiente
    return float(qty_decimal)
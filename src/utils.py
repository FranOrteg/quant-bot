# utils.py
import os
import json
import pandas as pd
import numpy as np
from binance.client import Client
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


def get_sellable_quantity(symbol: str, client: Client) -> float:
    info        = client.get_asset_balance(asset="BTC")
    free_btc    = Decimal(info["free"])

    symbol_info = client.get_symbol_info(symbol)
    lot_filter  = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size   = Decimal(lot_filter["stepSize"])
    min_qty     = Decimal(lot_filter["minQty"])

    # 🔍 Truncar a múltiplo exacto de stepSize (¡no usar round!)
    qty = (free_btc // step_size) * step_size

    if qty < min_qty:
        return 0.0

    return float(qty)


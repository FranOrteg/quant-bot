import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def log_operation(symbol, action, price, strategy_name, params, filename='logs/trades.csv'):
    os.makedirs('logs', exist_ok=True)
    file_exists = os.path.isfile(filename)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "strategy_name": strategy_name,
        "params": json.dumps(convert_params(params))
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

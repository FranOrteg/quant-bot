import os
import json
import pandas as pd
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
    return {k: (int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)) for k, v in params.items()}

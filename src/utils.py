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
        "params": json.dumps(params)
    }
    pd.DataFrame([data]).to_csv(filename, mode='a', index=False, header=not file_exists)

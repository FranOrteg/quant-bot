import ccxt
import pandas as pd
from datetime import datetime

def get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500):
    binance = ccxt.binance()
    ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

    
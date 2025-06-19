# src/strategy/rsi_sma.py

import pandas as pd

def rsi_sma_strategy(df, period_rsi=5, sma_period=10, rsi_buy=40, rsi_sell=60):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period_rsi).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period_rsi).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['SMA'] = df['close'].rolling(window=sma_period).mean()
    df['position'] = 0

    # Ahora las condiciones usan los parámetros variables:
    df.loc[(df['RSI'] < rsi_buy) & (df['close'] > df['SMA']), 'position'] = 1
    df.loc[(df['RSI'] > rsi_sell) & (df['close'] < df['SMA']), 'position'] = -1

    return df

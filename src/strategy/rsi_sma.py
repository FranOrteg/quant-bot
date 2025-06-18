# src/strategy/rsi_sma.py

import pandas as pd

def rsi_sma_strategy(df, period_rsi=14, sma_period=20):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period_rsi).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period_rsi).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['SMA'] = df['close'].rolling(window=sma_period).mean()

    df['position'] = 0
    df.loc[(df['RSI'] < 30) & (df['close'] > df['SMA']), 'position'] = 1
    df.loc[(df['RSI'] > 70) & (df['close'] < df['SMA']), 'position'] = -1

    return df

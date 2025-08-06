# src/strategy/rsi_sma.py
import pandas as pd

def rsi_sma_strategy(df, rsi_period=14, sma_period=10, rsi_buy=30, rsi_sell=70):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=rsi_period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df['SMA'] = df['close'].rolling(window=sma_period).mean()
    df['position'] = 0

    df.loc[(df['RSI'] < rsi_buy) & (df['close'] > df['SMA']), 'position'] = 1
    df.loc[(df['RSI'] > rsi_sell) & (df['close'] < df['SMA']), 'position'] = -1

    return df

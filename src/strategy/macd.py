import pandas as pd

def macd_strategy(df, short_ema=12, long_ema=26, signal_ema=9):
    df['EMA12'] = df['close'].ewm(span=short_ema, adjust=False).mean()
    df['EMA26'] = df['close'].ewm(span=long_ema, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=signal_ema, adjust=False).mean()

    df['position'] = 0
    df.loc[df['MACD'] > df['Signal'], 'position'] = 1
    df.loc[df['MACD'] < df['Signal'], 'position'] = -1

    return df

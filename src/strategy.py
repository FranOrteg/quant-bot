def moving_average_crossover(df, short_window=20, long_window=50):
    df['SMA20'] = df['close'].rolling(window=short_window).mean()
    df['SMA50'] = df['close'].rolling(window=long_window).mean()
    
    df['signal'] = 0
    df.loc[df.index[short_window:], 'signal'] = (
        df['SMA20'][short_window:] > df['SMA50'][short_window:]
    ).astype(int)

    
    df['position'] = df['signal'].diff()
    return df

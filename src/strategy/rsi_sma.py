# src/strategy/rsi_sma.py

import pandas as pd, numpy as np

def rsi_sma_strategy(df, rsi_period=14, sma_period=50, rsi_buy=25, rsi_sell=75, in_position=False, **_):
    # --- Indicadores (minúsculas para coherencia con el logger) ---
    delta = df['close'].diff()
    gain  = delta.where(delta > 0, 0).rolling(rsi_period, min_periods=rsi_period).mean()
    loss  = -delta.where(delta < 0, 0).rolling(rsi_period, min_periods=rsi_period).mean()
    rs    = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))

    df['sma'] = df['close'].rolling(sma_period, min_periods=sma_period).mean()
    df['ema200'] = df['close'].ewm(span=200, min_periods=200).mean()

    tr = pd.concat([
        (df['high'] - df['low']),
        (df['high'] - df['close'].shift()).abs(),
        (df['low']  - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['atr_pct'] = df['atr'] / df['close']

    # --- Señales con filtros de régimen y cruces ---
    rsi_up   = (df['rsi'].shift(1) < rsi_buy) & (df['rsi'] >= rsi_buy)   # cruce al alza
    rsi_down = (df['rsi'].shift(1) > rsi_sell) & (df['rsi'] <= rsi_sell) # cruce a la baja
    uptrend  = df['close'] >= df['ema200']

    # En uptrend, compro en pullback (cruce RSI); en downtrend permito mean-reversion muy extrema
    buy_condition  = (uptrend & rsi_up) | (~uptrend & (df['rsi'] <= min(25, rsi_buy)) & (df['close'] > df['sma']*1.002))

    # Salida: sobrecompra, pérdida de SMA con margen, o vela de -2% (stop bar) si estoy dentro
    stop_bar = df['close'] < df['close'].shift() * 0.98
    sell_condition = rsi_down | (df['close'] < df['sma']*0.995) | (in_position & stop_bar)

    df['signal_raw'] = np.select([buy_condition, sell_condition], [1, -1], default=0)

    # Lo que consume el bot:
    df['position'] = df['signal_raw']  # 1 compra, -1 venta, 0 hold
    df['reason'] = np.where(buy_condition, 'BUY:rsi_cross/uptrend OR MR',
                     np.where(sell_condition, 'SELL:rsi_cross OR <sma OR stop_bar', 'HOLD'))
    return df

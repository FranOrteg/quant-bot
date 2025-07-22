# src/strategy/multi_indicator.py
import pandas as pd
import numpy as np

def multi_indicator_strategy(df, 
                           # MACD params
                           macd_short=12, macd_long=26, macd_signal=9,
                           # RSI params  
                           rsi_period=14, rsi_oversold=30, rsi_overbought=70,
                           # Bollinger Bands params
                           bb_period=20, bb_std=2,
                           # Volume filter
                           volume_ma_period=20, volume_threshold=1.2):
    """
    Estrategia híbrida que combina MACD, RSI, Bandas de Bollinger y filtro de volumen
    
    Señales de compra:
    - MACD > Signal line
    - RSI < 70 (no sobrecomprado)
    - Precio cerca del límite inferior de Bollinger
    - Volumen > promedio * threshold
    
    Señales de venta:
    - MACD < Signal line
    - RSI > 30 (no sobrevendido)  
    - Precio cerca del límite superior de Bollinger
    """
    
    # MACD Calculation
    df['EMA_short'] = df['close'].ewm(span=macd_short).mean()
    df['EMA_long'] = df['close'].ewm(span=macd_long).mean()
    df['MACD'] = df['EMA_short'] - df['EMA_long']
    df['MACD_signal'] = df['MACD'].ewm(span=macd_signal).mean()
    df['MACD_histogram'] = df['MACD'] - df['MACD_signal']
    
    # RSI Calculation
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=rsi_period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['BB_middle'] = df['close'].rolling(window=bb_period).mean()
    df['BB_std'] = df['close'].rolling(window=bb_period).std()
    df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * bb_std)
    df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * bb_std)
    df['BB_position'] = (df['close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])
    
    # Volume Filter
    df['volume_ma'] = df['volume'].rolling(window=volume_ma_period).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    
    # Signal Generation
    df['position'] = 0
    
    # Buy signals (todas las condiciones deben cumplirse)
    buy_conditions = (
        (df['MACD'] > df['MACD_signal']) &  # MACD bullish
        (df['RSI'] < rsi_overbought) &      # No sobrecomprado
        (df['BB_position'] < 0.3) &         # Cerca del límite inferior BB
        (df['volume_ratio'] > volume_threshold) &  # Volumen alto
        (df['MACD_histogram'] > df['MACD_histogram'].shift(1))  # MACD histogram creciendo
    )
    
    # Sell signals
    sell_conditions = (
        (df['MACD'] < df['MACD_signal']) &  # MACD bearish
        (df['RSI'] > rsi_oversold) &        # No sobrevendido
        (df['BB_position'] > 0.7)           # Cerca del límite superior BB
    )
    
    df.loc[buy_conditions, 'position'] = 1
    df.loc[sell_conditions, 'position'] = -1
    
    # Añadir señales de confianza
    df['signal_strength'] = 0
    df.loc[buy_conditions, 'signal_strength'] = (
        abs(df['MACD'] - df['MACD_signal']) * 0.3 +
        (rsi_overbought - df['RSI']) * 0.3 +
        (0.3 - df['BB_position']) * 0.2 +
        (df['volume_ratio'] - volume_threshold) * 0.2
    )[buy_conditions]
    
    return df

def adaptive_multi_strategy(df, **kwargs):
    """
    Versión adaptativa que ajusta parámetros basándose en la volatilidad del mercado
    """
    # Calcular volatilidad
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=20).std()
    volatility_percentile = df['volatility'].rolling(window=100).quantile(0.7)
    
    # Ajustar parámetros según volatilidad
    current_vol = df['volatility'].iloc[-20:].mean()
    vol_threshold = volatility_percentile.iloc[-1] if not pd.isna(volatility_percentile.iloc[-1]) else current_vol
    
    if current_vol > vol_threshold:  # Alta volatilidad
        kwargs.update({
            'rsi_oversold': 25,      # Más estricto
            'rsi_overbought': 75,
            'volume_threshold': 1.5,  # Requiere más volumen
            'bb_std': 2.5            # Bandas más amplias
        })
    else:  # Baja volatilidad
        kwargs.update({
            'rsi_oversold': 35,      # Menos estricto
            'rsi_overbought': 65,
            'volume_threshold': 1.0,  # Menos volumen requerido
            'bb_std': 1.8            # Bandas más estrechas
        })
    
    return multi_indicator_strategy(df, **kwargs)

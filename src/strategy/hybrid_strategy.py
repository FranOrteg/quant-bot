# src/strategy/hybrid_strategy.py
import pandas as pd
import numpy as np

def hybrid_trading_strategy(df, 
                          # Parámetros más agresivos para generar más señales
                          macd_short=8, macd_long=21, macd_signal=5,
                          rsi_period=12, rsi_oversold=40, rsi_overbought=60,
                          bb_period=18, bb_std=1.8,
                          volume_threshold=0.8,  # Menos restrictivo
                          trend_ema=50):
    """
    Estrategia híbrida optimizada que combina múltiples indicadores
    con parámetros más agresivos para generar más señales de trading
    """
    df = df.copy()
    
    # === MACD ===
    df['ema_short'] = df['close'].ewm(span=macd_short).mean()
    df['ema_long'] = df['close'].ewm(span=macd_long).mean()
    df['macd'] = df['ema_short'] - df['ema_long']
    df['macd_signal'] = df['macd'].ewm(span=macd_signal).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    df['macd_bullish'] = df['macd'] > df['macd_signal']
    df['macd_growing'] = df['macd_histogram'] > df['macd_histogram'].shift(1)
    
    # === RSI ===
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=rsi_period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # === Bollinger Bands ===
    df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
    df['bb_std'] = df['close'].rolling(window=bb_period).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * bb_std)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * bb_std)
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    df['bb_squeeze'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] < 0.1  # Bandas estrechas
    
    # === Trend Filter ===
    df['trend_ema'] = df['close'].ewm(span=trend_ema).mean()
    df['uptrend'] = df['close'] > df['trend_ema']
    df['trend_strength'] = (df['close'] - df['trend_ema']) / df['trend_ema']
    
    # === Volume ===
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    df['volume_surge'] = df['volume_ratio'] > volume_threshold
    
    # === Price Action ===
    df['price_momentum'] = df['close'].pct_change(5)  # 5-period momentum
    df['volatility'] = df['close'].pct_change().rolling(20).std()
    
    # === Señales de Compra (múltiples condiciones) ===
    # Condición 1: MACD bullish momentum
    buy_condition_1 = (
        df['macd_bullish'] & 
        df['macd_growing'] & 
        (df['rsi'] < rsi_overbought) &
        df['uptrend']
    )
    
    # Condición 2: Oversold bounce
    buy_condition_2 = (
        (df['rsi'] < rsi_oversold + 5) &
        (df['bb_position'] < 0.2) &
        df['volume_surge'] &
        (df['price_momentum'] > -0.02)  # No está cayendo fuertemente
    )
    
    # Condición 3: Breakout pattern
    buy_condition_3 = (
        (df['close'] > df['bb_upper'].shift(1)) &  # Rompe banda superior
        df['volume_surge'] &
        df['uptrend'] &
        (df['rsi'] > 45) & (df['rsi'] < 75)
    )
    
    # Condición 4: Trend continuation
    buy_condition_4 = (
        df['uptrend'] &
        (df['trend_strength'] > 0.02) &  # Fuerte tendencia alcista
        (df['rsi'] > 35) & (df['rsi'] < 65) &
        df['macd_bullish']
    )
    
    # === Señales de Venta ===
    # Condición 1: MACD bearish
    sell_condition_1 = (
        ~df['macd_bullish'] &
        (df['macd_histogram'] < df['macd_histogram'].shift(1))
    )
    
    # Condición 2: Overbought
    sell_condition_2 = (
        (df['rsi'] > rsi_overbought) &
        (df['bb_position'] > 0.8)
    )
    
    # Condición 3: Trend reversal
    sell_condition_3 = (
        ~df['uptrend'] &
        (df['trend_strength'] < -0.015)
    )
    
    # Condición 4: Stop loss técnico
    sell_condition_4 = (
        (df['price_momentum'] < -0.03) &  # Caída fuerte
        (df['rsi'] < 40)
    )
    
    # === Combinar señales ===
    df['buy_signal'] = (
        buy_condition_1 | buy_condition_2 | 
        buy_condition_3 | buy_condition_4
    )
    
    df['sell_signal'] = (
        sell_condition_1 | sell_condition_2 | 
        sell_condition_3 | sell_condition_4
    )
    
    # === Generar posiciones ===
    df['position'] = 0
    df.loc[df['buy_signal'], 'position'] = 1
    df.loc[df['sell_signal'], 'position'] = -1
    
    # === Score de confianza ===
    df['signal_score'] = 0
    
    # Para señales de compra
    buy_mask = df['buy_signal']
    df.loc[buy_mask, 'signal_score'] = (
        df.loc[buy_mask, 'macd_bullish'].astype(int) * 0.25 +
        (df.loc[buy_mask, 'rsi'] < rsi_overbought).astype(int) * 0.25 +
        df.loc[buy_mask, 'uptrend'].astype(int) * 0.25 +
        df.loc[buy_mask, 'volume_surge'].astype(int) * 0.25
    )
    
    # Para señales de venta  
    sell_mask = df['sell_signal']
    df.loc[sell_mask, 'signal_score'] = (
        (~df.loc[sell_mask, 'macd_bullish']).astype(int) * 0.3 +
        (df.loc[sell_mask, 'rsi'] > rsi_overbought).astype(int) * 0.3 +
        (~df.loc[sell_mask, 'uptrend']).astype(int) * 0.4
    )
    
    # Filtrar señales de baja confianza
    confidence_threshold = 0.5
    df.loc[df['signal_score'] < confidence_threshold, 'position'] = 0
    
    return df

def scalping_strategy(df, fast_ema=5, slow_ema=15, rsi_period=7):
    """
    Estrategia de scalping para timeframes más cortos
    """
    df = df.copy()
    
    # EMAs rápidas
    df['ema_fast'] = df['close'].ewm(span=fast_ema).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_ema).mean()
    
    # RSI corto
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=rsi_period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Volume
    df['volume_sma'] = df['volume'].rolling(window=10).mean()
    df['volume_spike'] = df['volume'] > df['volume_sma'] * 1.5
    
    # Momentum
    df['momentum'] = df['close'].pct_change(3)
    
    # Señales
    df['position'] = 0
    
    # Buy: EMA cross up + RSI not overbought + volume
    buy_signal = (
        (df['ema_fast'] > df['ema_slow']) &
        (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1)) &  # Cross
        (df['rsi'] < 70) &
        df['volume_spike'] &
        (df['momentum'] > 0)
    )
    
    # Sell: EMA cross down or RSI overbought
    sell_signal = (
        ((df['ema_fast'] < df['ema_slow']) &
         (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))) |  # Cross
        (df['rsi'] > 80) |
        (df['momentum'] < -0.01)
    )
    
    df.loc[buy_signal, 'position'] = 1
    df.loc[sell_signal, 'position'] = -1
    
    return df

def momentum_breakout_strategy(df, lookback=20, breakout_threshold=0.02):
    """
    Estrategia de momentum y breakouts
    """
    df = df.copy()
    
    # Rolling high/low
    df['rolling_high'] = df['high'].rolling(window=lookback).max()
    df['rolling_low'] = df['low'].rolling(window=lookback).min()
    
    # Breakout signals
    df['breakout_up'] = df['close'] > df['rolling_high'].shift(1) * (1 + breakout_threshold)
    df['breakout_down'] = df['close'] < df['rolling_low'].shift(1) * (1 - breakout_threshold)
    
    # Volume confirmation
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['high_volume'] = df['volume'] > df['volume_sma'] * 1.2
    
    # Momentum
    df['momentum'] = df['close'].pct_change(5)
    df['strong_momentum'] = abs(df['momentum']) > 0.015
    
    # Signals
    df['position'] = 0
    
    # Buy on upward breakout with volume and momentum
    buy_signal = (
        df['breakout_up'] &
        df['high_volume'] &
        df['strong_momentum'] &
        (df['momentum'] > 0)
    )
    
    # Sell on downward breakout or momentum reversal
    sell_signal = (
        df['breakout_down'] |
        ((df['momentum'] < -0.02) & df['strong_momentum'])
    )
    
    df.loc[buy_signal, 'position'] = 1
    df.loc[sell_signal, 'position'] = -1
    
    return df

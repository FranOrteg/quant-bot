# src/strategy/rsi_sma.py - VERSION OPTIMIZADA
import pandas as pd
import numpy as np

def rsi_sma_strategy(df, rsi_period=14, sma_period=50, rsi_buy=25, rsi_sell=75):
    """
    Estrategia RSI-SMA OPTIMIZADA - Parámetros corregidos basados en análisis cuantitativo
    
    CAMBIOS CRÍTICOS:
    - RSI niveles: 30/70 → 25/75 (más extremos, menos whipsaws)
    - SMA period: 20 → 50 (mejor filtro de tendencia)
    - RSI period: 10 → 14 (estándar de la industria)
    """
    
    # Calcular RSI con método robusto
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=rsi_period, min_periods=rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=rsi_period, min_periods=rsi_period).mean()
    
    # Evitar división por cero
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # SMA más largo para filtro de tendencia robusto
    df['SMA'] = df['close'].rolling(window=sma_period, min_periods=sma_period).mean()
    
    # Inicializar posiciones
    df['position'] = 0
    
    # LÓGICA CORREGIDA - MÁS CONSERVADORA
    # Compra: RSI oversold + precio en uptrend
    buy_condition = (df['RSI'] < rsi_buy) & (df['close'] > df['SMA'])
    
    # Venta: RSI overbought OR ruptura de tendencia
    sell_condition = (df['RSI'] > rsi_sell) | (df['close'] < df['SMA'] * 0.985)
    
    df.loc[buy_condition, 'position'] = 1
    df.loc[sell_condition, 'position'] = -1
    
    return df

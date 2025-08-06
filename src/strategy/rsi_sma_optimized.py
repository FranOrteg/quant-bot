# src/strategy/rsi_sma_optimized.py
import pandas as pd
import numpy as np

def rsi_sma_optimized_strategy(df, rsi_period=14, sma_period=50, rsi_buy=25, rsi_sell=75, stop_loss_pct=0.02):
    """
    Estrategia RSI-SMA optimizada con gestión de riesgo mejorada
    
    Mejoras implementadas:
    1. RSI con niveles más extremos (25/75) para reducir falsos positivos
    2. SMA más largo (50) para filtrar mejor la tendencia
    3. Stop-loss dinámico integrado
    4. Lógica de señales más robusta
    """
    
    # Calcular RSI con método mejorado
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=rsi_period, min_periods=rsi_period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=rsi_period, min_periods=rsi_period).mean()
    
    # Evitar división por cero
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # SMA más largo para mejor filtro de tendencia
    df['SMA'] = df['close'].rolling(window=sma_period, min_periods=sma_period).mean()
    
    # ATR para volatility-adjusted signals
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = np.abs(df['high'] - df['close'].shift())
    df['low_close'] = np.abs(df['low'] - df['close'].shift())
    df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['ATR'] = df['true_range'].rolling(window=14).mean()
    
    # Inicializar posiciones
    df['position'] = 0
    
    # LÓGICA MEJORADA DE SEÑALES
    # Condiciones de compra MÁS restrictivas:
    # 1. RSI < 25 (realmente oversold)
    # 2. Precio > SMA (confirma uptrend)
    # 3. Volumen por encima de la media (confirma fuerza)
    if 'volume' in df.columns:
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        volume_condition = df['volume'] > df['volume_ma'] * 1.2
    else:
        volume_condition = True
    
    buy_condition = (
        (df['RSI'] < rsi_buy) & 
        (df['close'] > df['SMA']) &
        volume_condition
    )
    
    # Condiciones de venta MÁS robustas:
    # 1. RSI > 75 (realmente overbought) O
    # 2. Stop loss del 2% O
    # 3. Precio cae por debajo de SMA con margen
    sell_condition = (
        (df['RSI'] > rsi_sell) |
        (df['close'] < df['close'].shift() * (1 - stop_loss_pct)) |  # Stop loss
        (df['close'] < df['SMA'] * 0.985)  # Break below SMA with margin
    )
    
    df.loc[buy_condition, 'position'] = 1
    df.loc[sell_condition, 'position'] = -1
    
    # Añadir información de debugging
    df['buy_signal'] = buy_condition.astype(int)
    df['sell_signal'] = sell_condition.astype(int)
    
    return df

# Función de compatibilidad con el sistema actual
def rsi_sma_strategy(df, rsi_period=14, sma_period=50, rsi_buy=25, rsi_sell=75):
    return rsi_sma_optimized_strategy(df, rsi_period, sma_period, rsi_buy, rsi_sell)

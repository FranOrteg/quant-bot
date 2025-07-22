#!/usr/bin/env python3
# Diagnóstico de la estrategia multi-indicador

import pandas as pd
from src.strategy.multi_indicator import multi_indicator_strategy
from src.binance_api import get_historical_data

def test_strategy():
    print("🔍 DIAGNÓSTICO DE ESTRATEGIA MULTI-INDICADOR")
    print("=" * 50)
    
    # Obtener datos
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=1000)
    print(f"✅ Datos obtenidos: {len(df)} filas")
    
    # Aplicar estrategia con parámetros por defecto
    df_strategy = multi_indicator_strategy(df.copy())
    
    # Verificar indicadores
    print(f"\n📊 INDICADORES:")
    print(f"MACD válidos: {df_strategy['MACD'].notna().sum()}/{len(df_strategy)}")
    print(f"RSI válidos: {df_strategy['RSI'].notna().sum()}/{len(df_strategy)}")
    print(f"BB válidos: {df_strategy['BB_position'].notna().sum()}/{len(df_strategy)}")
    print(f"Volume válidos: {df_strategy['volume_ratio'].notna().sum()}/{len(df_strategy)}")
    
    # Verificar señales
    buy_signals = (df_strategy['position'] == 1).sum()
    sell_signals = (df_strategy['position'] == -1).sum()
    
    print(f"\n🎯 SEÑALES:")
    print(f"Señales de compra: {buy_signals}")
    print(f"Señales de venta: {sell_signals}")
    
    if buy_signals > 0:
        print("\n🔍 PRIMERAS 5 SEÑALES DE COMPRA:")
        buy_rows = df_strategy[df_strategy['position'] == 1].head()
        for idx, row in buy_rows.iterrows():
            print(f"  Fecha: {idx}, Precio: {row['close']:.2f}")
            print(f"    MACD: {row['MACD']:.4f} > Signal: {row['MACD_signal']:.4f}")
            print(f"    RSI: {row['RSI']:.2f}, BB_pos: {row['BB_position']:.3f}")
            print(f"    Volume_ratio: {row['volume_ratio']:.2f}")
    
    # Probar con parámetros más relajados
    print(f"\n🔧 PROBANDO CON PARÁMETROS RELAJADOS:")
    df_relaxed = multi_indicator_strategy(
        df.copy(),
        rsi_overbought=80,  # Más permisivo
        volume_threshold=0.8,  # Menos volumen requerido
        bb_std=1.5  # Bandas más estrechas
    )
    
    buy_relaxed = (df_relaxed['position'] == 1).sum()
    sell_relaxed = (df_relaxed['position'] == -1).sum()
    
    print(f"Señales de compra (relajadas): {buy_relaxed}")
    print(f"Señales de venta (relajadas): {sell_relaxed}")
    
    # Verificar condiciones individuales
    print(f"\n🧪 ANÁLISIS DE CONDICIONES:")
    df_test = df_strategy.copy()
    
    # Condiciones individuales
    macd_bullish = (df_test['MACD'] > df_test['MACD_signal']).sum()
    rsi_ok = (df_test['RSI'] < 70).sum()
    bb_low = (df_test['BB_position'] < 0.3).sum()
    volume_ok = (df_test['volume_ratio'] > 1.2).sum()
    macd_growing = (df_test['MACD_histogram'] > df_test['MACD_histogram'].shift(1)).sum()
    
    print(f"MACD bullish: {macd_bullish}")
    print(f"RSI < 70: {rsi_ok}")
    print(f"BB_position < 0.3: {bb_low}")
    print(f"Volume > 1.2x: {volume_ok}")
    print(f"MACD histogram creciendo: {macd_growing}")
    
    # Condiciones combinadas
    all_conditions = (
        (df_test['MACD'] > df_test['MACD_signal']) &
        (df_test['RSI'] < 70) &
        (df_test['BB_position'] < 0.3) &
        (df_test['volume_ratio'] > 1.2) &
        (df_test['MACD_histogram'] > df_test['MACD_histogram'].shift(1)) &
        df_test['MACD'].notna() &
        df_test['RSI'].notna() &
        df_test['BB_position'].notna() &
        df_test['volume_ratio'].notna()
    ).sum()
    
    print(f"TODAS las condiciones: {all_conditions}")
    
    return df_strategy

if __name__ == "__main__":
    df_result = test_strategy()

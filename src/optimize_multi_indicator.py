# src/optimize_multi_indicator.py
import pandas as pd
import numpy as np
from src.strategy.multi_indicator import multi_indicator_strategy, adaptive_multi_strategy
from src.risk_management import enhanced_backtest_with_risk_management
from src.binance_api import get_historical_data
import os
from datetime import datetime
from itertools import product
import json

def optimize_multi_indicator_strategy():
    """
    Optimización avanzada de la estrategia multi-indicador
    """
    print("🔄 Obteniendo datos históricos...")
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=1000)
    
    # Parámetros a optimizar
    param_ranges = {
        'macd_short': [8, 12, 16],
        'macd_long': [21, 26, 30],
        'macd_signal': [5, 9, 12],
        'rsi_period': [10, 14, 18],
        'rsi_oversold': [25, 30, 35],
        'rsi_overbought': [65, 70, 75],
        'bb_period': [15, 20, 25],
        'bb_std': [1.8, 2.0, 2.2],
        'volume_threshold': [1.0, 1.2, 1.5]
    }
    
    results = []
    total_combinations = np.prod([len(v) for v in param_ranges.values()])
    print(f"🧮 Probando {total_combinations} combinaciones...")
    
    # Generar todas las combinaciones
    param_names = list(param_ranges.keys())
    param_values = list(param_ranges.values())
    
    count = 0
    best_sharpe = -np.inf
    best_params = None
    
    for combination in product(*param_values):
        count += 1
        if count % 100 == 0:
            print(f"⏳ Progreso: {count}/{total_combinations} ({count/total_combinations*100:.1f}%)")
        
        params = dict(zip(param_names, combination))
        
        # Validar parámetros lógicos
        if params['macd_short'] >= params['macd_long']:
            continue
        if params['rsi_oversold'] >= params['rsi_overbought']:
            continue
        
        try:
            df_copy = df.copy()
            df_copy = multi_indicator_strategy(df_copy, **params)
            
            # Backtest con gestión de riesgo
            df_result, capital, metrics, trades_df = enhanced_backtest_with_risk_management(df_copy)
            
            # Filtrar resultados con pocas operaciones
            if metrics['total_trades'] < 5:
                continue
            
            result = {
                'strategy': 'multi_indicator',
                **params,
                'capital_final': round(capital, 2),
                'total_return': round(metrics['total_return'] * 100, 2),
                'sharpe_ratio': round(metrics['sharpe_ratio'], 3),
                'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
                'win_rate': round(metrics['win_rate'] * 100, 2),
                'profit_factor': round(metrics['profit_factor'], 3),
                'total_trades': metrics['total_trades'],
                'avg_win': round(metrics['avg_win'] * 100, 2),
                'avg_loss': round(metrics['avg_loss'] * 100, 2),
                'timestamp': datetime.now().isoformat()
            }
            
            results.append(result)
            
            # Tracking del mejor resultado
            if metrics['sharpe_ratio'] > best_sharpe and metrics['total_trades'] >= 10:
                best_sharpe = metrics['sharpe_ratio']
                best_params = params.copy()
                print(f"🎯 Nuevo mejor resultado: Sharpe={best_sharpe:.3f}, Return={metrics['total_return']*100:.2f}%")
        
        except Exception as e:
            print(f"❌ Error con parámetros {params}: {str(e)}")
            continue
    
    # Guardar resultados
    os.makedirs('results', exist_ok=True)
    results_df = pd.DataFrame(results)
    
    if not results_df.empty:
        results_df = results_df.sort_values('sharpe_ratio', ascending=False)
        results_df.to_csv('results/multi_indicator_optimization.csv', index=False)
        
        # Guardar top 5 resultados
        top_5 = results_df.head(5)
        print("\n🏆 TOP 5 RESULTADOS:")
        print(top_5[['capital_final', 'total_return', 'sharpe_ratio', 'max_drawdown', 
                     'win_rate', 'total_trades']].to_string(index=False))
        
        # Guardar mejores parámetros
        best_result = results_df.iloc[0].to_dict()
        with open('results/best_multi_indicator_params.json', 'w') as f:
            json.dump(best_result, f, indent=2)
        
        print(f"\n💾 Resultados guardados en results/multi_indicator_optimization.csv")
        print(f"💾 Mejores parámetros guardados en results/best_multi_indicator_params.json")
        
        return best_result
    else:
        print("❌ No se obtuvieron resultados válidos")
        return None

def test_adaptive_strategy():
    """
    Probar la estrategia adaptativa
    """
    print("\n🧪 Probando estrategia adaptativa...")
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=1000)
    
    # Estrategia fija vs adaptativa
    df_fixed = df.copy()
    df_adaptive = df.copy()
    
    # Aplicar estrategias
    df_fixed = multi_indicator_strategy(df_fixed)
    df_adaptive = adaptive_multi_strategy(df_adaptive)
    
    # Backtest
    _, capital_fixed, metrics_fixed, _ = enhanced_backtest_with_risk_management(df_fixed)
    _, capital_adaptive, metrics_adaptive, _ = enhanced_backtest_with_risk_management(df_adaptive)
    
    print("\n📊 COMPARACIÓN FIJA vs ADAPTATIVA:")
    print(f"Estrategia Fija: Return={metrics_fixed['total_return']*100:.2f}%, Sharpe={metrics_fixed['sharpe_ratio']:.3f}")
    print(f"Estrategia Adaptativa: Return={metrics_adaptive['total_return']*100:.2f}%, Sharpe={metrics_adaptive['sharpe_ratio']:.3f}")
    
    return {
        'fixed': metrics_fixed,
        'adaptive': metrics_adaptive
    }

if __name__ == "__main__":
    print("🚀 INICIANDO OPTIMIZACIÓN DE ESTRATEGIA MULTI-INDICADOR")
    print("=" * 60)
    
    # Optimizar estrategia
    best_result = optimize_multi_indicator_strategy()
    
    if best_result:
        print("\n" + "=" * 60)
        print("🧪 PROBANDO ESTRATEGIA ADAPTATIVA")
        comparison = test_adaptive_strategy()
        
        print("\n" + "=" * 60)
        print("✅ OPTIMIZACIÓN COMPLETADA")

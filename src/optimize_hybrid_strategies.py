# src/optimize_hybrid_strategies.py
import pandas as pd
import numpy as np
from src.strategy.hybrid_strategy import (
    hybrid_trading_strategy, 
    scalping_strategy, 
    momentum_breakout_strategy
)
from src.risk_management import enhanced_backtest_with_risk_management
from src.binance_api import get_historical_data
import os
from datetime import datetime
from itertools import product
import json

def optimize_hybrid_strategy():
    """
    Optimización de la estrategia híbrida principal
    """
    print("🚀 OPTIMIZANDO ESTRATEGIA HÍBRIDA")
    print("=" * 50)
    
    # Obtener datos
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=1000)
    print(f"✅ Datos obtenidos: {len(df)} filas")
    
    # Parámetros a optimizar (optimizados para velocidad y eficiencia)
    param_ranges = {
        'macd_short': [6, 8, 10],
        'macd_long': [20, 24],  # Reducido
        'macd_signal': [5, 6],  # Reducido
        'rsi_period': [12, 14],  # Reducido
        'rsi_oversold': [35, 40],  # Reducido
        'rsi_overbought': [60, 65],  # Reducido
        'bb_period': [18, 20],  # Reducido
        'bb_std': [1.8, 2.0],  # Reducido
        'volume_threshold': [0.7, 0.9],  # Reducido
        'trend_ema': [45, 55]  # Reducido
    }
    
    results = []
    total_combinations = np.prod([len(v) for v in param_ranges.values()])
    print(f"🧮 Probando {total_combinations} combinaciones...")
    
    param_names = list(param_ranges.keys())
    param_values = list(param_ranges.values())
    
    count = 0
    best_sharpe = -np.inf
    best_params = None
    
    for combination in product(*param_values):
        count += 1
        if count % 500 == 0:
            print(f"⏳ Progreso: {count}/{total_combinations} ({count/total_combinations*100:.1f}%)")
        
        params = dict(zip(param_names, combination))
        
        # Validar parámetros lógicos
        if params['macd_short'] >= params['macd_long']:
            continue
        if params['rsi_oversold'] >= params['rsi_overbought']:
            continue
        
        try:
            df_copy = df.copy()
            df_copy = hybrid_trading_strategy(df_copy, **params)
            
            # Backtest
            df_result, capital, metrics, trades_df = enhanced_backtest_with_risk_management(df_copy)
            
            # Filtrar resultados con pocas operaciones
            if metrics['total_trades'] < 3:
                continue
            
            result = {
                'strategy': 'hybrid',
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
            if metrics['sharpe_ratio'] > best_sharpe and metrics['total_trades'] >= 5:
                best_sharpe = metrics['sharpe_ratio']
                best_params = params.copy()
                print(f"🎯 Nuevo mejor resultado: Sharpe={best_sharpe:.3f}, Return={metrics['total_return']*100:.2f}%, Trades={metrics['total_trades']}")
        
        except Exception as e:
            print(f"❌ Error con parámetros {params}: {str(e)}")
            continue
    
    return process_results(results, 'hybrid')

def test_scalping_strategy():
    """
    Probar estrategia de scalping en diferentes timeframes
    """
    print("\n🏃 PROBANDO ESTRATEGIA DE SCALPING")
    print("=" * 50)
    
    # Probar en diferentes timeframes
    timeframes = ['15m', '30m', '1h']
    results = {}
    
    for tf in timeframes:
        print(f"\n📊 Timeframe: {tf}")
        try:
            df = get_historical_data(symbol='BTC/USDT', timeframe=tf, limit=1000)
            
            # Parámetros optimizados para scalping
            param_ranges = {
                'fast_ema': [3, 5, 7],
                'slow_ema': [12, 15, 18],
                'rsi_period': [5, 7, 9]
            }
            
            best_result = None
            best_sharpe = -np.inf
            
            for fast_ema in param_ranges['fast_ema']:
                for slow_ema in param_ranges['slow_ema']:
                    for rsi_period in param_ranges['rsi_period']:
                        if fast_ema >= slow_ema:
                            continue
                        
                        try:
                            df_copy = df.copy()
                            df_copy = scalping_strategy(df_copy, fast_ema, slow_ema, rsi_period)
                            
                            df_result, capital, metrics, trades_df = enhanced_backtest_with_risk_management(df_copy, timeframe=tf)
                            
                            if metrics['total_trades'] >= 5 and metrics['sharpe_ratio'] > best_sharpe:
                                best_sharpe = metrics['sharpe_ratio']
                                best_result = {
                                    'timeframe': tf,
                                    'fast_ema': fast_ema,
                                    'slow_ema': slow_ema,
                                    'rsi_period': rsi_period,
                                    'capital_final': round(capital, 2),
                                    'total_return': round(metrics['total_return'] * 100, 2),
                                    'sharpe_ratio': round(metrics['sharpe_ratio'], 3),
                                    'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
                                    'win_rate': round(metrics['win_rate'] * 100, 2),
                                    'total_trades': metrics['total_trades']
                                }
                        except:
                            continue
            
            if best_result:
                results[tf] = best_result
                print(f"✅ Mejor resultado {tf}: Return={best_result['total_return']}%, Sharpe={best_result['sharpe_ratio']}")
            else:
                print(f"❌ No hay resultados válidos para {tf}")
                
        except Exception as e:
            print(f"❌ Error obteniendo datos para {tf}: {str(e)}")
    
    return results

def test_momentum_breakout():
    """
    Probar estrategia de momentum breakout
    """
    print("\n💥 PROBANDO ESTRATEGIA MOMENTUM BREAKOUT")
    print("=" * 50)
    
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=1000)
    
    # Parámetros a probar
    lookback_periods = [15, 20, 25]
    breakout_thresholds = [0.015, 0.02, 0.025]
    
    best_result = None
    best_sharpe = -np.inf
    
    for lookback in lookback_periods:
        for threshold in breakout_thresholds:
            try:
                df_copy = df.copy()
                df_copy = momentum_breakout_strategy(df_copy, lookback, threshold)
                
                df_result, capital, metrics, trades_df = enhanced_backtest_with_risk_management(df_copy)
                
                if metrics['total_trades'] >= 3 and metrics['sharpe_ratio'] > best_sharpe:
                    best_sharpe = metrics['sharpe_ratio']
                    best_result = {
                        'lookback': lookback,
                        'breakout_threshold': threshold,
                        'capital_final': round(capital, 2),
                        'total_return': round(metrics['total_return'] * 100, 2),
                        'sharpe_ratio': round(metrics['sharpe_ratio'], 3),
                        'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
                        'win_rate': round(metrics['win_rate'] * 100, 2),
                        'total_trades': metrics['total_trades']
                    }
                    print(f"🎯 Nuevo mejor: Lookback={lookback}, Threshold={threshold:.3f}, Sharpe={best_sharpe:.3f}")
            except:
                continue
    
    return best_result

def process_results(results, strategy_name):
    """
    Procesar y guardar resultados
    """
    os.makedirs('results', exist_ok=True)
    results_df = pd.DataFrame(results)
    
    if not results_df.empty:
        results_df = results_df.sort_values('sharpe_ratio', ascending=False)
        results_df.to_csv(f'results/{strategy_name}_optimization.csv', index=False)
        
        # Top 5 resultados
        top_5 = results_df.head(5)
        print(f"\n🏆 TOP 5 RESULTADOS {strategy_name.upper()}:")
        print(top_5[['capital_final', 'total_return', 'sharpe_ratio', 'max_drawdown', 
                     'win_rate', 'total_trades']].to_string(index=False))
        
        # Guardar mejores parámetros
        best_result = results_df.iloc[0].to_dict()
        with open(f'results/best_{strategy_name}_params.json', 'w') as f:
            json.dump(best_result, f, indent=2)
        
        print(f"💾 Resultados guardados en results/{strategy_name}_optimization.csv")
        
        return best_result
    else:
        print(f"❌ No se obtuvieron resultados válidos para {strategy_name}")
        return None

def compare_all_strategies():
    """
    Comparar todas las estrategias en el mismo período
    """
    print("\n🏆 COMPARACIÓN DE TODAS LAS ESTRATEGIAS")
    print("=" * 60)
    
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=1000)
    
    strategies_to_test = [
        ("Híbrida", lambda d: hybrid_trading_strategy(d)),
        ("Scalping", lambda d: scalping_strategy(d)),
        ("Momentum", lambda d: momentum_breakout_strategy(d))
    ]
    
    comparison_results = []
    
    for name, strategy_func in strategies_to_test:
        try:
            df_copy = df.copy()
            df_strategy = strategy_func(df_copy)
            
            df_result, capital, metrics, trades_df = enhanced_backtest_with_risk_management(df_strategy)
            
            result = {
                'strategy': name,
                'capital_final': round(capital, 2),
                'total_return': round(metrics['total_return'] * 100, 2),
                'sharpe_ratio': round(metrics['sharpe_ratio'], 3),
                'max_drawdown': round(metrics['max_drawdown'] * 100, 2),
                'win_rate': round(metrics['win_rate'] * 100, 2),
                'total_trades': metrics['total_trades'],
                'profit_factor': round(metrics['profit_factor'], 3)
            }
            
            comparison_results.append(result)
            print(f"✅ {name}: Return={result['total_return']}%, Sharpe={result['sharpe_ratio']}, Trades={result['total_trades']}")
            
        except Exception as e:
            print(f"❌ Error con {name}: {str(e)}")
    
    # Guardar comparación
    if comparison_results:
        comp_df = pd.DataFrame(comparison_results)
        comp_df = comp_df.sort_values('sharpe_ratio', ascending=False)
        comp_df.to_csv('results/strategy_comparison.csv', index=False)
        
        print("\n📊 RANKING DE ESTRATEGIAS:")
        print(comp_df.to_string(index=False))
    
    return comparison_results

if __name__ == "__main__":
    print("🚀 INICIANDO OPTIMIZACIÓN RÁPIDA DE ESTRATEGIA HÍBRIDA")
    print("=" * 60)
    print("⚡ Modo optimizado: solo estrategia híbrida principal")
    print("⏰ Estimado: 5-10 minutos")
    print()
    
    # Solo optimizar estrategia híbrida principal
    start_time = datetime.now()
    hybrid_result = optimize_hybrid_strategy()
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds() / 60
    
    print("\n" + "=" * 60)
    print(f"✅ OPTIMIZACIÓN HÍBRIDA COMPLETADA en {duration:.1f} minutos")
    print("📁 Revisa la carpeta 'results' para ver los resultados")
    
    if hybrid_result:
        print("\n🎯 MEJOR CONFIGURACIÓN ENCONTRADA:")
        print(f"📈 Retorno Total: {hybrid_result['total_return']}%")
        print(f"📊 Sharpe Ratio: {hybrid_result['sharpe_ratio']}")
        print(f"📉 Max Drawdown: {hybrid_result['max_drawdown']}%")
        print(f"🎲 Win Rate: {hybrid_result['win_rate']}%")
        print(f"💰 Profit Factor: {hybrid_result['profit_factor']}")
        print(f"🔄 Total Trades: {hybrid_result['total_trades']}")
    
    print("\n💡 TIP: Para probar otras estrategias, ejecuta las funciones individuales")

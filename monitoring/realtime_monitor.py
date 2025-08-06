#!/usr/bin/env python3
# monitoring/realtime_monitor.py
import json
import os
import sys
from datetime import datetime, timezone

def get_current_balances():
    """Obtener balances actuales"""
    try:
        with open("logs/balance.json", 'r') as f:
            balance_15m = json.load(f)
        with open("logs/balance_5m.json", 'r') as f:
            balance_5m = json.load(f)
        return balance_15m, balance_5m
    except Exception as e:
        print(f"Error leyendo balances: {e}")
        return {}, {}

def count_recent_signals():
    """Contar señales generadas desde la optimización"""
    optimization_time = "2025-08-06T13:22"
    
    signal_count_15m = 0
    signal_count_5m = 0
    
    # Contar señales en logs
    try:
        with open("logs/live_trader.log", 'r') as f:
            lines = f.readlines()
            for line in lines:
                if optimization_time in line and ("COMPRA" in line or "VENTA" in line):
                    signal_count_15m += 1
    except:
        pass
        
    try:
        with open("logs/live_trader_5m.log", 'r') as f:
            lines = f.readlines()
            for line in lines:
                if optimization_time in line and ("COMPRA" in line or "VENTA" in line):
                    signal_count_5m += 1
    except:
        pass
    
    return signal_count_15m, signal_count_5m

def main():
    print("🔬 MONITOREO EN TIEMPO REAL - PARÁMETROS OPTIMIZADOS")
    print("=" * 60)
    
    # Cargar baseline
    try:
        with open("monitoring/baseline_metrics.json", 'r') as f:
            baseline = json.load(f)
        optimization_start = baseline["optimization_start"]
        print(f"📅 Optimización iniciada: {optimization_start}")
    except:
        print("❌ No se encontró baseline. Ejecutar performance_tracker.py primero")
        return
    
    # Estado actual
    balance_15m, balance_5m = get_current_balances()
    signals_15m, signals_5m = count_recent_signals()
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    print(f"🕐 Timestamp actual: {current_time}")
    print()
    
    # Bot 15m (Real Trading)
    print("🤖 BOT 15M (REAL TRADING)")
    print("-" * 30)
    baseline_15m = baseline["pre_optimization"]["bot_15m"]
    current_usdc_15m = balance_15m.get("USDC", baseline_15m["balance_usdc"])
    current_btc_15m = balance_15m.get("BTC", 0)
    
    change_15m = current_usdc_15m - baseline_15m["balance_usdc"]
    change_pct_15m = (change_15m / baseline_15m["balance_usdc"]) * 100 if baseline_15m["balance_usdc"] > 0 else 0
    
    print(f"💰 Balance USDC: {current_usdc_15m:.2f} (cambio: {change_15m:+.2f}, {change_pct_15m:+.2f}%)")
    print(f"₿  Balance BTC: {current_btc_15m:.8f}")
    print(f"📊 Señales nuevas: {signals_15m}")
    print(f"📈 Baseline return: {baseline_15m['total_return']:.2f}%")
    print()
    
    # Bot 5m (Testnet)
    print("🤖 BOT 5M (TESTNET)")
    print("-" * 30)
    baseline_5m = baseline["pre_optimization"]["bot_5m"]
    current_usdc_5m = balance_5m.get("USDC", baseline_5m["balance_usdc"])
    current_btc_5m = balance_5m.get("BTC", 0)
    
    change_5m = current_usdc_5m - baseline_5m["balance_usdc"]
    change_pct_5m = (change_5m / baseline_5m["balance_usdc"]) * 100 if baseline_5m["balance_usdc"] > 0 else 0
    
    print(f"💰 Balance USDC: {current_usdc_5m:.2f} (cambio: {change_5m:+.2f}, {change_pct_5m:+.2f}%)")
    print(f"₿  Balance BTC: {current_btc_5m:.8f}")
    print(f"📊 Señales nuevas: {signals_5m}")
    print(f"📈 Baseline return: {baseline_5m['total_return']:.2f}%")
    print()
    
    # Parámetros optimizados
    print("⚙️  PARÁMETROS OPTIMIZADOS")
    print("-" * 30)
    optimized = baseline["optimized_params"]
    for key, value in optimized.items():
        if key != "expected_improvement":
            print(f"   {key}: {value}")
    print()
    
    # Evaluación general
    total_signals = signals_15m + signals_5m
    if total_signals == 0:
        print("✅ EXCELENTE: Sin señales prematuras - parámetros funcionando como se esperaba")
    elif total_signals <= 2:
        print("✅ BUENO: Muy pocas señales - reducción exitosa de whipsaws")
    else:
        print("⚠️  REVISAR: Más señales de las esperadas - posible ajuste necesario")
    
    print("\n💡 Monitorear durante 48-72h para validación completa")

if __name__ == "__main__":
    main()

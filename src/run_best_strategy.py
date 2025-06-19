# src/run_best_strategy.py

from src.strategy_selector import select_best_strategy
from src.backtest import backtest_signals
from src.binance_api import get_historical_data
from src.strategy import moving_average_crossover, rsi_sma_strategy, macd_strategy
import matplotlib.pyplot as plt
import os

def run_best_strategy():
    best = select_best_strategy()
    strategy = best["strategy"]
    params = best["params"]

    # Obtener datos reales
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=500)

    # Aplicar estrategia con sus parámetros óptimos
    if strategy == "moving_average":
        df = moving_average_crossover(df, **params)
    elif strategy == "rsi_sma":
        df = rsi_sma_strategy(df, **params)
    elif strategy == "macd":
        df = macd_strategy(df, **params)
    else:
        raise ValueError(f"Estrategia no reconocida: {strategy}")

    # Backtest
    df, final_capital, metrics = backtest_signals(df)

    # Mostrar resultados
    print(f"\n🏆 Estrategia aplicada: {strategy}")
    print(f"📊 Parámetros: {params}")
    print(f"💰 Capital final: ${final_capital:.2f}")
    print(f"📈 Retorno total: {metrics['total_return']*100:.2f}%")
    print(f"📉 Máx. Drawdown: {metrics['max_drawdown']*100:.2f}%")
    print(f"⚖️ Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

    # Guardar gráfico
    os.makedirs("results", exist_ok=True)
    plt.figure(figsize=(12, 6))
    plt.plot(df["timestamp"], df["equity"], label="Equity Curve")
    plt.title(f"Backtest: {strategy}")
    plt.xlabel("Fecha")
    plt.ylabel("Capital ($)")
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.savefig("results/run_best_equity_curve.png")
    print("✅ Gráfico guardado en: results/run_best_equity_curve.png")

if __name__ == "__main__":
    run_best_strategy()

from binance_api import get_historical_data
from strategy import moving_average_crossover
from backtest import backtest_signals
import matplotlib.pyplot as plt

def run():
    df = get_historical_data()
    df = moving_average_crossover(df)
    df, final_capital, metrics = backtest_signals(df)

    print(df[['timestamp', 'close', 'position', 'equity']].tail(10))
    print(f"\n💰 Capital final: {final_capital:.2f} USD")
    print(f"📊 Retorno total: {metrics['total_return']:.2%}")
    print(f"📉 Máx. drawdown: {metrics['max_drawdown']:.2%}")
    print(f"📈 Sharpe ratio: {metrics['sharpe_ratio']:.2f}")

    plt.figure(figsize=(12, 6))
    plt.plot(df['timestamp'], df['equity'], label='Equity Curve')
    plt.title('Simulación Backtest')
    plt.xlabel('Fecha')
    plt.ylabel('Capital ($)')
    plt.grid(True)
    plt.legend()
    plt.savefig('logs/equity_curve.png')

if __name__ == "__main__":
    run()

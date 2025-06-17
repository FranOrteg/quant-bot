from binance_api import get_historical_data
from strategy import moving_average_crossover
import matplotlib.pyplot as plt

def run():
    df = get_historical_data()
    df = moving_average_crossover(df)

    print(df[['timestamp', 'close', 'SMA20', 'SMA50', 'signal', 'position']].tail(10))
    
    # Visualización simple
    plt.figure(figsize=(14, 7))
    plt.plot(df['timestamp'], df['close'], label='Close')
    plt.plot(df['timestamp'], df['SMA20'], label='SMA20')
    plt.plot(df['timestamp'], df['SMA50'], label='SMA50')
    plt.legend()
    plt.title("Cruce de Medias Móviles BTC/USDT")
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    run()

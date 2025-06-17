import numpy as np

def backtest_signals(df, initial_capital=10000):
    capital = initial_capital
    position = 0
    entry_price = 0
    equity_curve = []

    for i in range(len(df)):
        price = df.iloc[i]['close']
        signal = df.iloc[i]['position']

        if signal == 1 and position == 0:
            position = 1
            entry_price = price
        elif signal == -1 and position == 1:
            pnl = (price - entry_price) / entry_price
            capital *= (1 + pnl)
            position = 0

        equity_curve.append(capital)

    df['equity'] = equity_curve

    # Métricas
    total_return = (df['equity'].iloc[-1] / initial_capital) - 1
    df['returns'] = df['equity'].pct_change().fillna(0)
    sharpe_ratio = np.mean(df['returns']) / np.std(df['returns']) * np.sqrt(252)
    rolling_max = df['equity'].cummax()
    drawdown = (df['equity'] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    metrics = {
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown
    }

    return df, capital, metrics

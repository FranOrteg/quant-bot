# src/backtest.py

import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import os

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

    total_return = (df['equity'].iloc[-1] / initial_capital) - 1
    df['returns'] = df['equity'].pct_change().fillna(0)
    std_returns = np.std(df['returns'])

    if std_returns == 0:
        sharpe_ratio = 0
    else:
        sharpe_ratio = np.mean(df['returns']) / std_returns * np.sqrt(252)

    rolling_max = df['equity'].cummax()
    drawdown = (df['equity'] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    metrics = {
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown
    }

    return df, capital, metrics

def generate_equity_plot(df, filename='results/equity_curve.png'):
    plt.figure(figsize=(10, 5))
    plt.plot(df['timestamp'], df['equity'], label='Equity Curve')
    plt.title('Evolución del Capital')
    plt.xlabel('Fecha')
    plt.ylabel('Capital ($)')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def generate_pdf_report(df, capital_final, metrics, strategy_name='Estrategia', filename='results/report.pdf'):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Informe de Backtest: {strategy_name}", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Capital final: ${capital_final:,.2f}", ln=True)
    pdf.cell(200, 10, txt=f"Retorno total: {metrics['total_return']*100:.2f}%", ln=True)
    pdf.cell(200, 10, txt=f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}", ln=True)
    pdf.cell(200, 10, txt=f"Máximo Drawdown: {metrics['max_drawdown']*100:.2f}%", ln=True)

    # Insertar gráfico
    image_path = 'results/best_rsi_equity_curve.png'
    if os.path.exists(image_path):
        pdf.image(image_path, x=10, y=80, w=190)

    pdf.output(filename)

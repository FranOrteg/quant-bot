# src/backtest.py
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import os

# ➊  factor de anualización según la resolución de la vela
ANNUALIZATION = {
    "1d":   252,          # 252 días bursátiles
    "4h":  24*365/4,
    "1h":  24*365,
    "30m": 24*2*365,
    "15m": 24*4*365,
    "5m":  24*12*365,
}

def backtest_signals(df, initial_capital=10_000, timeframe="1h"):
    capital, position, entry_price = initial_capital, 0, 0
    equity_curve = []
    FEE, SLIPPAGE = 0.00075, 0.0004          # 0.075 % / 0.04 %

    for _, row in df.iterrows():
        price   = row["close"]
        signal  = row["position"]

        if signal == 1 and position == 0:                       # ---- BUY ----
            position, entry_price = 1, price * (1 + SLIPPAGE)
            capital *= (1 - FEE)

        elif signal == -1 and position == 1:                    # ---- SELL ---
            exit_price = price * (1 - SLIPPAGE)
            pnl        = (exit_price - entry_price) / entry_price
            capital   *= (1 + pnl) * (1 - FEE)
            position   = 0

        equity_curve.append(capital)

    df["equity"]  = equity_curve
    df["returns"] = df["equity"].pct_change().fillna(0)

    # ➋  Sharpe ratio con annualization dinámico
    mean_r, std_r = df["returns"].mean(), df["returns"].std()
    ann_factor    = ANNUALIZATION.get(timeframe, 252)
    sharpe_ratio  = 0 if std_r == 0 else mean_r / std_r * np.sqrt(ann_factor)

    rolling_max   = df["equity"].cummax()
    max_drawdown  = ((df["equity"] - rolling_max) / rolling_max).min()
    total_return  = df["equity"].iloc[-1] / initial_capital - 1

    metrics = {
        "total_return": total_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
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

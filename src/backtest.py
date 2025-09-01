# src/backtest.py
import os
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF

# ➊  factor de anualización según la resolución de la vela
ANNUALIZATION = {
    "1d":   252,            # 252 días bursátiles
    "4h":  24*365/4,
    "1h":  24*365,
    "30m": 24*2*365,
    "15m": 24*4*365,
    "5m":  24*12*365,
}

# ➋  costes (mismos defaults que paper/live)
FEE_RATE_DEFAULT   = float(os.getenv("BACKTEST_FEE_RATE", os.getenv("REAL_FEE_RATE", "0.001")))   # 0.1%
SLIPPAGE_DEFAULT   = float(os.getenv("BACKTEST_SLIPPAGE", "0.0005"))                              # 0.05%

def backtest_signals(df, initial_capital=10_000, timeframe="1h",
                     fee_rate: float = FEE_RATE_DEFAULT,
                     slippage: float = SLIPPAGE_DEFAULT):
    """
    Backtest simple long-only con señales en df['position'] ∈ {1,0,-1}.
    - Aplica costes simétricos a la entrada/salida:
      * fee_rate: comisión proporcional
      * slippage: deslizamiento proporcional
    """
    capital, position, entry_price = initial_capital, 0, 0.0
    equity_curve = []

    for _, row in df.iterrows():
        price  = float(row["close"])
        signal = int(row["position"])

        if signal == 1 and position == 0:          # ---- BUY ----
            fill_price = price * (1 + slippage)
            capital   *= (1 - fee_rate)
            position, entry_price = 1, fill_price

        elif signal == -1 and position == 1:       # ---- SELL ---
            exit_price = price * (1 - slippage)
            pnl        = (exit_price - entry_price) / entry_price
            capital   *= (1 + pnl) * (1 - fee_rate)
            position   = 0

        equity_curve.append(capital)

    df["equity"]  = equity_curve
    df["returns"] = df["equity"].pct_change().fillna(0)

    # Sharpe ratio con annualization dinámico
    mean_r, std_r = df["returns"].mean(), df["returns"].std()
    ann_factor    = ANNUALIZATION.get(timeframe, 252)
    sharpe_ratio  = 0.0 if std_r == 0 else mean_r / std_r * np.sqrt(ann_factor)

    rolling_max   = df["equity"].cummax()
    max_drawdown  = ((df["equity"] - rolling_max) / rolling_max).min()
    total_return  = df["equity"].iloc[-1] / initial_capital - 1

    metrics = {
        "total_return": float(total_return),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": float(max_drawdown),
    }
    return df, float(capital), metrics


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

    # Insertar gráfico si existe
    image_path = 'results/best_rsi_equity_curve.png'
    if os.path.exists(image_path):
        pdf.image(image_path, x=10, y=80, w=190)

    pdf.output(filename)

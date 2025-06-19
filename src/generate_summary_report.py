# src/generate_summary_report.py

import pandas as pd
import os
from src.report import generate_pdf_report

TRADES_PATH = 'logs/trades.csv'
CHART_PATH = 'results/trade_analysis.png'
OUTPUT_PATH = 'results/summary_report.pdf'

# Leer trades
trades = pd.read_csv(TRADES_PATH)
trades['timestamp'] = pd.to_datetime(trades['timestamp'], errors='coerce')
trades.dropna(subset=['timestamp', 'price', 'action'], inplace=True)

# Separar BUY y SELL
buy_trades = trades[trades['action'] == 'BUY']
sell_trades = trades[trades['action'] == 'SELL']

# Métricas
total_ops = len(trades)
buys = len(buy_trades)
sells = len(sell_trades)

metrics = {
    'total_operaciones': total_ops,
    'buy': buys,
    'sell': sells
}

if buys == sells and buys > 0:
    profit_ops = (sell_trades['price'].values - buy_trades['price'].values)
    metrics['retorno_total'] = profit_ops.sum()
    metrics['porcentaje_total'] = (profit_ops / buy_trades['price'].values * 100).sum()
else:
    metrics['retorno_total'] = 0.0
    metrics['porcentaje_total'] = 0.0

# Llamar al generador del PDF
generate_pdf_report(
    strategy_name="RSI + SMA Crossover",
    metrics=metrics,
    chart_path=CHART_PATH,
    output_path=OUTPUT_PATH
)

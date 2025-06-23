# src/generate_summary_report.py

import pandas as pd
import os
from src.report import generate_pdf_report

TRADES_PATH = 'logs/trades.csv'
CHART_PATH = 'results/trade_analysis.png'
OUTPUT_PATH = 'results/summary_report.pdf'

def generate_summary_report():
    if not os.path.exists(TRADES_PATH):
        print(f"❌ No se encontró el archivo de trades: {TRADES_PATH}")
        return

    trades = pd.read_csv(TRADES_PATH)
    trades['timestamp'] = pd.to_datetime(trades['timestamp'], errors='coerce')
    trades.dropna(subset=['timestamp', 'price', 'action'], inplace=True)

    buy_trades = trades[trades['action'] == 'BUY']
    sell_trades = trades[trades['action'] == 'SELL']

    total_ops = len(trades)
    buys = len(buy_trades)
    sells = len(sell_trades)
    paired_ops = min(buys, sells)

    metrics = {
        'total_operaciones': total_ops,
        'buy': buys,
        'sell': sells
    }

    if paired_ops > 0:
        buy_prices = buy_trades['price'].values[:paired_ops]
        sell_prices = sell_trades['price'].values[:paired_ops]
        profit_ops = sell_prices - buy_prices
        metrics['retorno_total'] = round(profit_ops.sum(), 2)
        metrics['porcentaje_total'] = round((profit_ops / buy_prices * 100).sum(), 2)
    else:
        metrics['retorno_total'] = 0.0
        metrics['porcentaje_total'] = 0.0

    generate_pdf_report(
        strategy_name="RSI + SMA Crossover",
        metrics=metrics,
        chart_path=CHART_PATH,
        output_path=OUTPUT_PATH
    )
    
    print(f"✅ Informe PDF generado en: {OUTPUT_PATH}")
    return OUTPUT_PATH

if __name__ == "__main__":
    generate_summary_report()

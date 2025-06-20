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

    # Generar PDF
    generate_pdf_report(
        strategy_name="RSI + SMA Crossover",
        metrics=metrics,
        chart_path=CHART_PATH,
        output_path=OUTPUT_PATH
    )
    
    print(f"✅ Informe PDF generado en: {OUTPUT_PATH}")
    return OUTPUT_PATH

# Solo para pruebas locales (opcional)
if __name__ == "__main__":
    generate_summary_report()

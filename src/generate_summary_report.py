# src/generate_summary_report.py

import pandas as pd
import os
from src.report import generate_pdf_report
from src.analyze_equity import generate_equity_chart

TRADES_PATH = 'logs/trades.csv'
PERF_PATH = 'logs/performance_log.csv'
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
        'sell': sells,
        'retorno_total': 0.0,
        'porcentaje_total': 0.0
    }

    if paired_ops > 0:
        buy_prices = buy_trades['price'].values[:paired_ops]
        sell_prices = sell_trades['price'].values[:paired_ops]
        profit_ops = sell_prices - buy_prices
        metrics['retorno_total'] = round(profit_ops.sum(), 2)
        metrics['porcentaje_total'] = round((profit_ops / buy_prices * 100).sum(), 2)

    # 🔁 Si existe performance_log.csv, generamos gráfico real
    if os.path.exists(PERF_PATH):
        print("📈 Generando gráfico de equity...")
        generate_equity_chart(TRADES_PATH, CHART_PATH)

    generate_pdf_report(
        strategy_name="RSI + SMA Crossover",
        metrics=metrics,
        chart_path=CHART_PATH if os.path.exists(CHART_PATH) else None,
        output_path=OUTPUT_PATH
    )
    
    print(f"✅ Informe PDF generado en: {OUTPUT_PATH}")
    return OUTPUT_PATH

if __name__ == "__main__":
    generate_summary_report()

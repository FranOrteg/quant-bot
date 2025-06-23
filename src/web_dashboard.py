# src/web_dashboard.py

from flask import Flask, jsonify, render_template_string, send_file
import pandas as pd
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TRADES_PATH = os.path.join(BASE_DIR, 'logs/trades.csv')
PRICE_PATH = os.path.join(BASE_DIR, 'data/BTCUSDT.csv')
REPORT_PATH = os.path.join(BASE_DIR, 'results/summary_report.pdf')

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <title>QuantBot Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: sans-serif; padding: 2rem; background: #f9f9f9; }
    canvas { max-width: 100%; }
    .info { margin-top: 2rem; }
    .button { margin-top: 1rem; display: inline-block; background: #007BFF; color: white; padding: 0.5rem 1rem; text-decoration: none; border-radius: 5px; }
  </style>
</head>
<body>
  <h1>📊 QuantBot Dashboard</h1>
  <canvas id="priceChart"></canvas>
  <div class="info">
    <p><strong>Total operaciones:</strong> {{ total_ops }} ({{ buys }} BUY, {{ sells }} SELL)</p>
    <p><strong>Retorno acumulado:</strong> {{ total_profit }} USD</p>
    <p><strong>Porcentaje acumulado:</strong> {{ profit_pct }}%</p>
    <a href="/download_report" class="button">📄 Descargar Informe PDF</a>
  </div>
  <script>
    const labels = {{ timestamps|safe }};
    const prices = {{ closes|safe }};
    const buySignals = {{ buy_signals|safe }};
    const sellSignals = {{ sell_signals|safe }};

    const ctx = document.getElementById('priceChart');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          { label: 'BTCUSDT', data: prices, borderColor: 'blue', fill: false },
          { label: 'BUY', data: buySignals, backgroundColor: 'green', type: 'scatter', pointStyle: 'triangle', pointRadius: 6 },
          { label: 'SELL', data: sellSignals, backgroundColor: 'red', type: 'scatter', pointStyle: 'rectRot', pointRadius: 6 }
        ]
      },
      options: { scales: { x: { display: false } } }
    });
  </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    trades = pd.read_csv(TRADES_PATH)
    prices = pd.read_csv(PRICE_PATH, names=['timestamp', 'close'], header=None)

    trades['timestamp'] = pd.to_datetime(trades['timestamp'], utc=True, errors='coerce')
    prices['timestamp'] = pd.to_datetime(prices['timestamp'], utc=True, errors='coerce')

    buy_trades = trades[trades['action'] == 'BUY']
    sell_trades = trades[trades['action'] == 'SELL']

    timestamps = prices['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    closes = prices['close'].tolist()

    buy_signals = [{'x': ts.strftime('%Y-%m-%d %H:%M:%S'), 'y': price} for ts, price in zip(buy_trades['timestamp'], buy_trades['price'])]
    sell_signals = [{'x': ts.strftime('%Y-%m-%d %H:%M:%S'), 'y': price} for ts, price in zip(sell_trades['timestamp'], sell_trades['price'])]

    if len(buy_trades) == len(sell_trades):
        profit_ops = (sell_trades['price'].values - buy_trades['price'].values)
        total_profit = round(profit_ops.sum(), 2)
        profit_pct = round((profit_ops / buy_trades['price'].values * 100).sum(), 2)
    else:
        total_profit = '⚠️ Desbalance'
        profit_pct = '⚠️'

    return render_template_string(TEMPLATE,
        timestamps=timestamps,
        closes=closes,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        total_ops=len(trades),
        buys=len(buy_trades),
        sells=len(sell_trades),
        total_profit=total_profit,
        profit_pct=profit_pct
    )

@app.route('/download_report')
def download_report():
    if os.path.exists(REPORT_PATH):
        return send_file(REPORT_PATH, as_attachment=True)
    return "No se ha generado el informe aún.", 404
  
@app.route("/balance")
def show_balance():
    from src.balance_tracker import load_balance
    return jsonify(load_balance())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)


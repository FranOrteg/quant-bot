# src/report.py

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def generate_pdf_report(strategy_name, metrics, chart_path='results/equity_curve.png', output_path='results/report.pdf'):
    os.makedirs('results', exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "📈 Informe de Backtest")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Estrategia: {strategy_name}")
    c.drawString(50, height - 100, f"Fecha: {now}")

    y = height - 140
    for key, value in metrics.items():
        c.drawString(50, y, f"{key.replace('_', ' ').capitalize()}: {value:.4f}")
        y -= 20

    # Añadir imagen del gráfico
    if os.path.exists(chart_path):
        c.drawImage(chart_path, 50, 100, width=500, preserveAspectRatio=True, mask='auto')

    c.showPage()
    c.save()

    print(f"✅ Informe PDF generado en: {output_path}")

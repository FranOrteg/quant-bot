# src/performance_logger.py
from datetime import datetime
from src.daily_performance import calculate_daily_performance

def run_logger():
    now = datetime.now()
    print(f"🕒 Ejecutando logger a las {now.strftime('%Y-%m-%d %H:%M:%S')}")
    calculate_daily_performance()

if __name__ == "__main__":
    run_logger()

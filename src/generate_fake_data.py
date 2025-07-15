# scripts/generate_fake_data.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(42)

start = datetime(2024, 1, 1)
rows = 200  # 🟢 Esto garantiza suficiente data para RSI y SMA
prices = [20000 + np.random.normal(0, 100) for _ in range(rows)]
timestamps = [start + timedelta(minutes=5*i) for i in range(rows)]

df = pd.DataFrame({'timestamp': timestamps, 'close': prices})
os.makedirs('data', exist_ok=True)
df.to_csv('data/BTCUSDC.csv', index=False)

print("✅ Datos simulados generados en data/BTCUSDC.csv")

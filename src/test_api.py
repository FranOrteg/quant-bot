# test_api.py
import os
from dotenv import load_dotenv

load_dotenv()

print("BINANCE_API_KEY:", os.getenv("BINANCE_API_KEY"))
print("BINANCE_API_SECRET:", os.getenv("BINANCE_API_SECRET"))

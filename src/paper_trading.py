# src/paper_trading.py
import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret, testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'

symbol = "BTCUSDT"
quantity = 0.001  # ajusta según balance simulado

def get_price():
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def buy():
    order = client.create_order(
        symbol=symbol,
        side='BUY',
        type='MARKET',
        quantity=quantity
    )
    print(f"✅ ORDEN COMPRA: {order}")
    return order

def sell():
    order = client.create_order(
        symbol=symbol,
        side='SELL',
        type='MARKET',
        quantity=quantity
    )
    print(f"✅ ORDEN VENTA: {order}")
    return order

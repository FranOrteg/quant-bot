import os
from binance.client import Client
from dotenv import load_dotenv
from src.utils import log_operation  # 🔁 ahora importamos desde utils

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret, testnet=True)
client.API_URL = 'https://testnet.binance.vision/api'

quantity = 0.001  # ajusta según balance simulado

def get_price(symbol="BTCUSDT"):
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def buy(symbol, price, strategy_name, params):
    order = client.create_order(
        symbol=symbol,
        side='BUY',
        type='MARKET',
        quantity=quantity
    )
    print(f"✅ ORDEN COMPRA: {order}")
    log_operation(symbol, "BUY", price, strategy_name, params)
    return order

def sell(symbol, price, strategy_name, params):
    order = client.create_order(
        symbol=symbol,
        side='SELL',
        type='MARKET',
        quantity=quantity
    )
    print(f"✅ ORDEN VENTA: {order}")
    log_operation(symbol, "SELL", price, strategy_name, params)
    return order

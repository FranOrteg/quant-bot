# src/utils.py
import os
import json
import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

TRADES_FILE = 'logs/trades.csv'
PERFORMANCE_FILE = 'logs/performance_log.csv'

# Moneda de caja (equity) tomada del entorno; por defecto USDC
QUOTE_ASSET = os.getenv("QUOTE_ASSET", "USDC").upper()

def log_operation(symbol, action, price, strategy_name, params, filename=None):
    """
    Guarda una operación (BUY/SELL) con la estrategia y parámetros usados.
    """
    os.makedirs('logs', exist_ok=True)
    if filename is None:
        filename = TRADES_FILE  # default: logs/trades.csv

    file_exists = os.path.isfile(filename)
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "action": action,
        "price": float(price),
        "strategy": strategy_name,
        "params": json.dumps(convert_params(params)),
    }
    pd.DataFrame([data]).to_csv(filename, mode='a', index=False, header=not file_exists)

def log_performance(action, price, balance, filename=None):
    """
    Registra un snapshot de performance:
    - Usa QUOTE_ASSET para el cash (USDC/USDT/…).
    - Mantiene columna 'USDT' por compatibilidad (se rellena con el mismo cash).
    - Equity = cash + BTC * price
    """
    os.makedirs('logs', exist_ok=True)
    if filename is None:
        filename = PERFORMANCE_FILE  # default: logs/performance_log.csv

    file_exists = os.path.isfile(filename)

    # Extrae cash y btc del dict balance (acepta floats o Decimal)
    cash = _to_float(balance.get(QUOTE_ASSET, balance.get("USDT", 0.0)))
    btc  = _to_float(balance.get("BTC", 0.0))
    px   = _to_float(price)
    equity = cash + btc * px

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "price": px,
        # Columna con el nombre real del quote asset (USDC/USDT/…)
        QUOTE_ASSET: cash,
        # Compatibilidad con CSVs/dashboards existentes
        "USDT": cash,
        "BTC": btc,
        "equity": equity,
    }
    pd.DataFrame([data]).to_csv(filename, mode='a', index=False, header=not file_exists)

def convert_params(params):
    def sanitize(v):
        if isinstance(v, (int, float, str)):
            return v
        if isinstance(v, (np.integer, np.floating)):
            return v.item()
        return str(v)
    return {k: sanitize(v) for k, v in params.items()}

def get_sellable_quantity(symbol: str, client: Client) -> Decimal:
    """
    Calcula la cantidad vendible respetando LOT_SIZE y (MIN_)NOTIONAL.
    Devuelve Decimal("0.0") si no cumple mínimos.
    """
    info = client.get_asset_balance(asset="BTC")
    free_btc = Decimal(info["free"])

    # Filtros del símbolo
    symbol_info = client.get_symbol_info(symbol)
    lot_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size = Decimal(lot_filter["stepSize"])
    min_qty   = Decimal(lot_filter["minQty"])

    # NOTIONAL o MIN_NOTIONAL
    notional_filter = next(
        (f for f in symbol_info["filters"] if f["filterType"] in ("NOTIONAL", "MIN_NOTIONAL")),
        None
    )
    min_notional = Decimal(notional_filter["minNotional"]) if notional_filter else Decimal("0")

    # Margen de seguridad 0.5% para evitar problemas por redondeos
    free_btc_with_margin = free_btc * Decimal("0.995")

    # Truncar a múltiplo exacto de step_size (sin redondeo al alza)
    steps = (free_btc_with_margin / step_size).to_integral_value(rounding=ROUND_DOWN)
    qty = steps * step_size

    if qty < min_qty:
        print(f"❌ Cantidad {qty} es menor que minQty {min_qty}")
        return Decimal("0.0")

    if min_notional > 0:
        ticker = client.get_symbol_ticker(symbol=symbol)
        current_price = Decimal(ticker["price"])
        if qty * current_price < min_notional:
            print(f"❌ Valor {qty * current_price} < minNotional {min_notional}")
            return Decimal("0.0")

    print(f"✅ Cantidad calculada: {qty} BTC (libre: {free_btc}, step: {step_size})")
    return qty

def format_quantity_for_binance(quantity: Decimal, step_size: Decimal) -> str:
    """
    Formatea cantidad respetando step_size, truncando (ROUND_DOWN) y evitando notación científica.
    """
    q = quantity.quantize(step_size, rounding=ROUND_DOWN)
    # Representación fija (sin e-notation) y sin recortes indebidos de ceros
    return format(q, 'f')

def _to_float(x) -> float:
    if isinstance(x, Decimal):
        return float(x)
    return float(x or 0.0)

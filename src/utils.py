# utils.py
import os
import json
import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from math import floor

TRADES_FILE = 'logs/trades.csv'
PERFORMANCE_FILE = 'logs/performance_log.csv'

def log_operation(symbol, action, price, strategy_name, params, filename=None):
    os.makedirs('logs', exist_ok=True)
    if filename is None:
        filename = TRADES_FILE  # default: logs/trades.csv

    file_exists = os.path.isfile(filename)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "strategy": strategy_name,
        "params": json.dumps(convert_params(params))
    }

    pd.DataFrame([data]).to_csv(filename, mode='a', index=False, header=not file_exists)

def log_performance(action, price, balance, filename=None):
    os.makedirs('logs', exist_ok=True)
    if filename is None:
        filename = PERFORMANCE_FILE  # default: logs/performance_log.csv

    file_exists = os.path.isfile(filename)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "price": price,
        "USDT": balance.get("USDT", 0.0),
        "BTC": balance.get("BTC", 0.0),
        "equity": balance.get("USDT", 0.0) + balance.get("BTC", 0.0) * price
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
    Calcula la cantidad vendible de BTC respetando los filtros de Binance.
    
    Args:
        symbol: Par de trading (ej: BTCUSDC)
        client: Cliente de Binance
        
    Returns:
        Decimal: Cantidad vendible de BTC, o Decimal("0.0") si no cumple los mínimos
    """
    info = client.get_asset_balance(asset="BTC")
    free_btc = Decimal(info["free"])
    
    # Obtener filtros del símbolo
    symbol_info = client.get_symbol_info(symbol)
    lot_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size = Decimal(lot_filter["stepSize"])
    min_qty = Decimal(lot_filter["minQty"])
    
    # Obtener filtro NOTIONAL
    notional_filter = next((f for f in symbol_info["filters"] if f["filterType"] == "NOTIONAL"), None)
    min_notional = Decimal(notional_filter["minNotional"]) if notional_filter else Decimal("0")
    
    # Aplicar margen de seguridad del 0.5% para evitar problemas de redondeo
    safety_margin = Decimal("0.995")
    free_btc_with_margin = free_btc * safety_margin
    
    # Truncar a múltiplo exacto de stepSize
    qty = (free_btc_with_margin // step_size) * step_size
    
    # Verificar cantidad mínima
    if qty < min_qty:
        print(f"❌ Cantidad {qty} es menor que minQty {min_qty}")
        return Decimal("0.0")
    
    # Verificar valor mínimo de la operación (NOTIONAL)
    if min_notional > 0:
        ticker = client.get_symbol_ticker(symbol=symbol)
        current_price = Decimal(ticker["price"])
        notional_value = qty * current_price
        
        if notional_value < min_notional:
            print(f"❌ Valor de operación {notional_value} USDC es menor que minNotional {min_notional} USDC")
            return Decimal("0.0")
    
    print(f"✅ Cantidad calculada: {qty} BTC (libre: {free_btc}, step: {step_size})")
    return qty


def format_quantity_for_binance(quantity: Decimal, step_size: Decimal) -> str:
    """
    Formatea una cantidad para enviar a Binance respetando el stepSize.
    
    Args:
        quantity: Cantidad como Decimal
        step_size: Tamaño del paso como Decimal
        
    Returns:
        str: Cantidad formateada como string
    """
    # Determinar la precisión basada en el step_size
    if step_size == Decimal("0.00001000"):  # BTCUSDC
        return f"{quantity:.5f}"
    elif step_size == Decimal("0.00000100"):
        return f"{quantity:.6f}"
    elif step_size == Decimal("0.00000010"):
        return f"{quantity:.7f}"
    elif step_size == Decimal("0.00000001"):
        return f"{quantity:.8f}"
    else:
        # Para otros casos, usar la precisión del step_size
        decimals = abs(step_size.as_tuple().exponent)
        return f"{quantity:.{decimals}f}"

# src/real_trading.py
import os
import pandas as pd
from decimal import Decimal, ROUND_DOWN
from binance.client import Client
from dotenv import load_dotenv

from src.utils import (
    log_operation,
    get_sellable_quantity,
    format_quantity_for_binance,
)
from src.balance_tracker import update_balance
from src.alert import send_trade_email, send_trade_telegram

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
USE_TESTNET = os.getenv("USE_BINANCE_TESTNET", "False") == "True"

# Cliente Binance (con testnet opcional)
try:
    client = Client(api_key, api_secret, testnet=USE_TESTNET)
    if USE_TESTNET:
        client.API_URL = "https://testnet.binance.vision/api"
    client.ping()
except Exception as e:
    print(f"❌ Binance API error al iniciar: {e}")
    client = None

# Parámetros por defecto (puedes moverlos a .env si quieres)
DEFAULT_BUY_QTY = Decimal(os.getenv("REAL_BUY_QTY", "0.0002"))
FEE_RATE = Decimal(os.getenv("REAL_FEE_RATE", "0.001"))  # aprox/fallback

def _get_symbol_filters(symbol: str):
    """Devuelve (step_size, min_qty, min_notional) como Decimal."""
    info = client.get_symbol_info(symbol)
    lot = next(f for f in info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size = Decimal(lot["stepSize"])
    min_qty = Decimal(lot["minQty"])

    # NOTIONAL ha ido migrando a MIN_NOTIONAL en muchos pares; soporta ambos
    notional = next(
        (f for f in info["filters"] if f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL")),
        None,
    )
    min_notional = Decimal(notional["minNotional"]) if notional else Decimal("0")

    return step_size, min_qty, min_notional

def _vwap_and_commission(order, fallback_price: Decimal, fallback_qty: Decimal):
    """
    Calcula VWAP real y comisión total (si la API la devuelve en el mismo asset de cotización).
    Si no hay 'fills' o no es posible, usa fallbacks razonables.
    """
    fills = order.get("fills", []) or []
    if not fills:
        # Fallback plano
        return float(fallback_price), float(fallback_qty), float(fallback_price * fallback_qty * FEE_RATE)

    notional = Decimal("0")
    qty_sum = Decimal("0")
    commission_quote = Decimal("0")
    quote_asset = None

    for f in fills:
        px = Decimal(str(f["price"]))
        q  = Decimal(str(f["qty"]))
        notional += px * q
        qty_sum  += q

        # intenta sumar comisión si está en el asset de cotización
        if "commission" in f and "commissionAsset" in f:
            if quote_asset is None:
                quote_asset = f["commissionAsset"]
            if f["commissionAsset"] == quote_asset and quote_asset in ("USDT", "USDC", "BUSD", "FDUSD", "TUSD"):
                commission_quote += Decimal(str(f["commission"]))

    if qty_sum > 0:
        vwap = notional / qty_sum
    else:
        vwap = fallback_price

    # Si no pudimos sumar comisiones en el asset de cotización, usa fallback por FEE_RATE
    fee = commission_quote if commission_quote > 0 else (vwap * qty_sum * FEE_RATE)

    return float(vwap), float(qty_sum), float(fee)

def buy(symbol, price, strategy_name, params, trades_path, perf_path):
    """
    Lanza una orden de compra a mercado. Valida minNotional y LOT_SIZE.
    Usa VWAP real y comisiones reportadas por Binance si están disponibles.
    """
    if client is None:
        print("⛔ No se puede ejecutar COMPRA: Binance no disponible")
        return None

    try:
        step_size, min_qty, min_notional = _get_symbol_filters(symbol)

        # Precio actual para validar notional mínimo
        ticker = client.get_symbol_ticker(symbol=symbol)
        last_px = Decimal(ticker["price"])

        qty = DEFAULT_BUY_QTY

        # Verificación de minQty
        if qty < min_qty:
            print(f"❌ Cantidad {qty} < minQty {min_qty}")
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},BUY_SKIPPED,{last_px},{qty},0,BELOW_MIN_QTY\n")
            return None

        # Verificación de minNotional
        if min_notional > 0 and qty * last_px < min_notional:
            print(f"❌ Notional {qty * last_px} < minNotional {min_notional}. Ajusta REAL_BUY_QTY.")
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},BUY_SKIPPED,{last_px},{qty},0,BELOW_MIN_NOTIONAL\n")
            return None

        # Formateo a step_size (truncar hacia abajo)
        qty_str = format_quantity_for_binance(qty, step_size)

        print(f"🟢 Ejecutando compra de {qty_str} {symbol}…")
        order = client.order_market_buy(symbol=symbol, quantity=qty_str)

        vwap, filled_qty, fee = _vwap_and_commission(
            order,
            fallback_price=last_px,
            fallback_qty=Decimal(qty_str)
        )

        # Logs de performance y operación
        with open(perf_path, "a") as f:
            f.write(f"{pd.Timestamp.utcnow().isoformat()},BUY,{vwap},{filled_qty},{vwap * filled_qty},SUCCESS\n")

        print(f"🟢 ORDEN REAL DE COMPRA ejecutada VWAP {vwap:.2f} (qty {filled_qty:.6f}, fee≈ {fee:.4f})")

        log_operation(symbol, "BUY", vwap, strategy_name, params, trades_path)
        update_balance("BUY", filled_qty, vwap + (fee / max(filled_qty, 1e-12)))
        send_trade_email("BUY", vwap, filled_qty, strategy_name, symbol)
        send_trade_telegram("BUY", vwap, filled_qty, strategy_name, symbol)

        return order

    except Exception as e:
        print(f"❌ Error al ejecutar compra real: {e}")
        try:
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},BUY_FAILED,{price},0,0,{str(e).replace(',', '')}\n")
        except Exception:
            pass
        return None

def sell(symbol, price, strategy_name, params, trades_path, perf_path):
    """
    Vende toda la cantidad vendible (respetando LOT_SIZE y minNotional).
    Usa VWAP real y comisiones reportadas por Binance si están disponibles.
    """
    if client is None:
        print("⛔ No se puede ejecutar VENTA: Binance no disponible")
        return None

    try:
        qty_decimal = get_sellable_quantity(symbol, client)

        if qty_decimal <= Decimal("0"):
            free_btc = client.get_asset_balance(asset="BTC")["free"]
            print(f"❌ Saldo ({free_btc} BTC) insuficiente o no vendible.")
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL_SKIPPED,{price},{free_btc},0,BELOW_MIN_QTY\n")
            return None

        # Formatear cantidad según stepSize
        step_size, _, _ = _get_symbol_filters(symbol)
        qty_str = format_quantity_for_binance(qty_decimal, step_size)
        print(f"🔴 Ejecutando venta de {qty_str} {symbol}…")

        order = client.order_market_sell(symbol=symbol, quantity=qty_str)

        # Precio/qty/fee reales
        ticker = client.get_symbol_ticker(symbol=symbol)
        last_px = Decimal(ticker["price"])

        vwap, filled_qty, fee = _vwap_and_commission(
            order,
            fallback_price=last_px,
            fallback_qty=Decimal(qty_str)
        )

        log_operation(symbol, "SELL", vwap, strategy_name, params, trades_path)
        update_balance("SELL", filled_qty, vwap - (fee / max(filled_qty, 1e-12)))
        send_trade_email("SELL", vwap, filled_qty, strategy_name, symbol)
        send_trade_telegram("SELL", vwap, filled_qty, strategy_name, symbol)

        with open(perf_path, "a") as f:
            f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL,{vwap},{filled_qty},{vwap * filled_qty},SUCCESS\n")

        print(f"✅ Venta ejecutada VWAP {vwap:.2f} (qty {filled_qty:.6f}, fee≈ {fee:.4f})")
        return order

    except Exception as e:
        print(f"❌ Error al vender: {e}")
        try:
            with open(perf_path, "a") as f:
                f.write(f"{pd.Timestamp.utcnow().isoformat()},SELL_FAILED,{price},-,0,{str(e).replace(',', '')}\n")
        except Exception:
            pass
        return None

# src/balance_tracker.py
import os
import json
from decimal import Decimal
from dotenv import load_dotenv

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from src.utils import log_performance

load_dotenv()

BALANCE_FILE = 'logs/balance.json'

# Activo de referencia para efectivo (depende de tu símbolo: BTCUSDC → USDC)
QUOTE_ASSET = os.getenv("QUOTE_ASSET", "USDC").upper()

# Balance simulado por defecto (para paper)
DEFAULT_BALANCE = {
    QUOTE_ASSET: float(os.getenv("DEFAULT_CASH", "10000")),
    "BTC": 0.0,
}

USE_REAL_BALANCE = os.getenv("USE_REAL_BALANCE", "False").strip() == "True"
USE_BINANCE_TESTNET = os.getenv("USE_BINANCE_TESTNET", "False").strip() == "True"
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "").strip()  # e.g. https://api.binance.us
API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()

print(f"🔍 USE_REAL_BALANCE: {USE_REAL_BALANCE}")
if USE_REAL_BALANCE:
    print(f"🔍 USE_BINANCE_TESTNET: {USE_BINANCE_TESTNET}")
    if BINANCE_BASE_URL:
        print(f"🔍 BINANCE_BASE_URL: {BINANCE_BASE_URL}")

def _build_client() -> Client:
    """
    Construye el cliente de Binance considerando testnet/base_url si se han definido por ENV.
    - USE_BINANCE_TESTNET=True → usa testnet oficial de spot.
    - BINANCE_BASE_URL → fuerza endpoint (p. ej., binance.us).
    """
    kwargs = {}
    if USE_BINANCE_TESTNET:
        # python-binance usa esta URL para testnet spot
        kwargs["testnet"] = True
    if BINANCE_BASE_URL:
        kwargs["base_url"] = BINANCE_BASE_URL
    client = Client(API_KEY, API_SECRET, **kwargs)
    return client

def _explain_2015_hint():
    return (
        "Posibles causas del -2015:\n"
        " • IP no autorizada para esta API key (revisa whitelist en Binance).\n"
        " • Permisos insuficientes: faltan permisos de Spot & Margin Trading o solo lectura.\n"
        " • Endpoint incorrecto: estás usando binance.com con una clave de binance.us (o viceversa), "
        "   o estás en testnet con una clave de mainnet.\n"
        " • Variables de entorno mal cargadas: revisa BINANCE_API_KEY/BINANCE_API_SECRET.\n"
        " • Cuenta con restricciones/KYC incompleto."
    )

def fetch_binance_balance():
    if not API_KEY or not API_SECRET:
        raise RuntimeError(
            "Faltan credenciales: define BINANCE_API_KEY y BINANCE_API_SECRET en tu entorno/.env."
        )

    client = _build_client()

    # Prueba rápida de conectividad/estado (no firmada)
    try:
        _ = client.get_exchange_info()
    except BinanceRequestException as e:
        raise RuntimeError(f"No hay conectividad con el endpoint de Binance ({e}). "
                           f"Revisa internet/firewall/DNS y BINANCE_BASE_URL si aplica.")
    except Exception as e:
        # No falla la ejecución: solo informamos
        print(f"⚠️ Aviso: fallo en get_exchange_info(): {e}")

    # Llamada firmada: aquí aparecen los -2015 de permisos/IP
    try:
        account_info = client.get_account()
    except BinanceAPIException as e:
        if e.code == -2015:
            hint = _explain_2015_hint()
            raise RuntimeError(f"APIError -2015: Invalid API-key, IP, or permissions.\n{hint}")
        else:
            raise RuntimeError(f"Fallo en get_account() → {e}")
    except Exception as e:
        raise RuntimeError(f"Error inesperado en get_account(): {e}")

    # Parseo de balances
    cash = Decimal("0")
    btc = Decimal("0")
    for asset in account_info.get('balances', []):
        if asset['asset'].upper() == QUOTE_ASSET:
            cash = Decimal(asset['free'])
        elif asset['asset'].upper() == 'BTC':
            btc = Decimal(asset['free'])

    balance = {
        QUOTE_ASSET: float(round(cash, 2)),
        "BTC": float(round(btc, 8)),
    }
    return balance

def load_balance():
    """
    Devuelve balance real (si USE_REAL_BALANCE=True) o paper (persistido en JSON).
    Si falla la consulta real (p. ej., -2015), informa y hace fallback a paper para que
    el bot no muera mientras investigas la configuración.
    """
    if USE_REAL_BALANCE:
        try:
            balance = fetch_binance_balance()
            print(f"✅ Balance real desde Binance: {balance}")
            return balance
        except Exception as e:
            print("❌ No se pudo obtener balance real de Binance.")
            print(str(e))
            print("🔁 Haciendo FALLBACK a balance simulado (paper) para continuar.")
            # Si no existe, crea uno por defecto
            if not os.path.exists(BALANCE_FILE):
                save_balance(DEFAULT_BALANCE)
            with open(BALANCE_FILE, 'r') as f:
                return json.load(f)

    # Modo paper
    if not os.path.exists(BALANCE_FILE):
        save_balance(DEFAULT_BALANCE)
    with open(BALANCE_FILE, 'r') as f:
        return json.load(f)

def save_balance(balance):
    os.makedirs(os.path.dirname(BALANCE_FILE), exist_ok=True)
    with open(BALANCE_FILE, 'w') as f:
        json.dump(balance, f, indent=2)

def update_balance(action, quantity, price):
    """
    En modo real no tocamos nada (se consulta de Binance).
    En modo paper actualizamos y registramos en performance.
    """
    if USE_REAL_BALANCE:
        return

    balance = load_balance()
    qty = float(quantity)
    px = float(price)

    if action == "BUY":
        cost = qty * px
        if balance.get(QUOTE_ASSET, 0.0) >= cost:
            balance[QUOTE_ASSET] -= cost
            balance["BTC"] = balance.get("BTC", 0.0) + qty
    elif action == "SELL":
        if balance.get("BTC", 0.0) >= qty:
            balance["BTC"] -= qty
            balance[QUOTE_ASSET] = balance.get(QUOTE_ASSET, 0.0) + qty * px

    save_balance(balance)
    log_performance(action, px, {**balance, "USDT": balance.get("USDT", 0.0)})  # compat
    print_balance(balance)

def print_balance(balance):
    print(f"💰 Balance actual: {balance}")

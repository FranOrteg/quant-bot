# src/binance_api.py
import ccxt
import pandas as pd
from typing import List, Any

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN DEL EXCHANGE (solo para histórico; no necesita API keys)
# ──────────────────────────────────────────────────────────────────────────────
exchange = ccxt.binance({
    "enableRateLimit": True,  # respeta límites de la API
})


# ──────────────────────────────────────────────────────────────────────────────
#  UTILIDADES
# ──────────────────────────────────────────────────────────────────────────────
def _normalize_ccxt_symbol(sym: str) -> str:
    """
    Acepta 'BTCUSDC' o 'BTC/USDC' y devuelve el formato CCXT 'BASE/QUOTE'.
    """
    if "/" in sym:
        return sym
    candidates = ("USDT", "USDC", "BUSD", "EUR", "BTC", "ETH")
    for q in candidates:
        if sym.endswith(q):
            base = sym[:-len(q)]
            if base:  # evita cadenas vacías
                return f"{base}/{q}"
    return sym  # fallback (CCXT lanzará error si no es válido)


def _rows_to_dataframe(rows: List[List[Any]]) -> pd.DataFrame:
    df = pd.DataFrame(
        rows,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    # Tipos y limpieza
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = (
        df.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
          .drop_duplicates(subset=["timestamp"], keep="last")
          .sort_values("timestamp")
          .reset_index(drop=True)
    )
    return df


# ──────────────────────────────────────────────────────────────────────────────
#  FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def get_historical_data(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 500,
) -> pd.DataFrame:
    """
    Devuelve un DataFrame OHLCV con hasta `limit` velas más recientes.
    Pagina hacia atrás si `limit` > 1_000 (máx por llamada en Binance via CCXT).

    - Acepta `symbol` con o sin barra (p.ej. 'BTCUSDC' o 'BTC/USDC').
    - Devuelve columnas: timestamp (UTC), open, high, low, close, volume.
    """
    symbol = _normalize_ccxt_symbol(symbol)
    if limit <= 0:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    ms_per_bar = exchange.parse_timeframe(timeframe) * 1_000
    all_rows: List[List[Any]] = []

    # 1) Primer tramo: velas más recientes
    batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=None, limit=min(1000, limit))
    if not batch:
        raise RuntimeError(f"Binance no devolvió datos para {symbol} {timeframe}")

    all_rows.extend(batch)
    earliest_ts = batch[0][0]  # timestamp del primer elemento (más antiguo del tramo)

    # 2) Tramos adicionales hacia atrás
    while len(all_rows) < limit:
        fetch = min(1000, limit - len(all_rows))
        # desplazamos 'since' hacia atrás un colchón para evitar solapes
        since = int(earliest_ts - ms_per_bar * (fetch + 1))

        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=fetch)
        if not batch:
            break

        # prepend para mantener orden cronológico en all_rows
        all_rows = batch + all_rows
        earliest_ts = batch[0][0]

        if len(batch) < fetch:  # ya no hay más histórico
            break

    # 3) Recorta exactamente al tamaño solicitado y limpia
    all_rows = all_rows[-limit:]
    df = _rows_to_dataframe(all_rows)
    # Asegura último recorte (por si tras limpieza sobran/faltan por duplicados)
    if len(df) > limit:
        df = df.iloc[-limit:].reset_index(drop=True)
    return df

# src/binance_api.py
import ccxt
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN DEL EXCHANGE
# ──────────────────────────────────────────────────────────────────────────────
exchange = ccxt.binance({
    "enableRateLimit": True,          # respeta los límites de la API
    # si usas claves:
    # "apiKey": "...",
    # "secret": "...",
})


# ──────────────────────────────────────────────────────────────────────────────
#  FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def get_historical_data(
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 500,
) -> pd.DataFrame:
    """
    Devuelve un DataFrame OHLCV con hasta `limit` barras más recientes,
    paginando hacia atrás si `limit` > 1 000 (máx. por llamada en Binance).
    """
    ms_per_bar = exchange.parse_timeframe(timeframe) * 1_000
    all_rows   = []

    # --- primera llamada: barras más recientes --------------------------------
    batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                 since=None, limit=min(1000, limit))
    if not batch:
        raise RuntimeError("Binance no devolvió datos")

    all_rows.extend(batch)
    earliest_ts = batch[0][0]      # timestamp del primer elemento (más antiguo)

    # --- llamadas adicionales mientras falten filas ---------------------------
    while len(all_rows) < limit:
        # Pedimos el siguiente tramo desplazando 'since' hacia atrás
        since = earliest_ts - ms_per_bar * 1_001   # 1 extra para no solapar
        fetch   = min(1000, limit - len(all_rows))

        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                     since=since, limit=fetch)
        if not batch:
            break

        all_rows = batch + all_rows                 # prepend para mantener orden
        earliest_ts = batch[0][0]

        if len(batch) < fetch:      # Binance ya no tiene más histórico
            break

    # --- recorta exactamente al tamaño pedido (por si se pasó) ----------------
    all_rows = all_rows[-limit:]

    # --- DataFrame final -------------------------------------------------------
    df = pd.DataFrame(
        all_rows,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df

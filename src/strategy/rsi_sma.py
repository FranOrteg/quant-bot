# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

def rsi_sma_strategy(
    df: pd.DataFrame,
    rsi_period: int = 21,
    sma_period: int = 30,
    rsi_buy: int = 40,
    rsi_sell: int = 70,
    lookback_bars: int = 8,
    in_position: bool = False,
    **_,
):
    """
    RSI + SMA long-only con 'recuperación de uptrend':
    - Si el RSI estuvo por debajo de rsi_buy en las últimas `lookback_bars` velas,
      y ahora vuelve el uptrend (precio > EMA200 y > SMA) con RSI subiendo,
      permitimos la ENTRADA aunque el cruce exacto ya ocurriera antes.
    - Salidas conservadoras: sobrecompra, pérdida de SMA (margen) o 'stop bar'.

    Columnas devueltas clave:
      - position:  1=BUY, -1=SELL, 0=HOLD (impulso de 1 vela)
      - signal_raw: igual que position (para debug)
      - reason: texto con motivo
      - rsi, sma, ema200, atr, atr_pct: indicadores auxiliares
    """
    if df.empty:
        return df

    # --- Indicadores base -----------------------------------------------------
    delta = df["close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(rsi_period, min_periods=rsi_period).mean()
    loss  = -delta.where(delta < 0, 0).rolling(rsi_period, min_periods=rsi_period).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    df["sma"]    = df["close"].rolling(sma_period, min_periods=sma_period).mean()
    df["ema200"] = df["close"].ewm(span=200, min_periods=200, adjust=False).mean()

    tr = pd.concat(
        [
            (df["high"] - df["low"]),
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(14, min_periods=14).mean()
    df["atr_pct"] = (df["atr"] / df["close"]).replace([np.inf, -np.inf], np.nan)

    # --- Regímenes y condiciones auxiliares ----------------------------------
    uptrend      = df["close"] >= df["ema200"]
    above_sma    = df["close"] > df["sma"]
    rsi_up_cross = (df["rsi"].shift(1) < rsi_buy) & (df["rsi"] >= rsi_buy)
    rsi_rising   = df["rsi"].diff() > 0

    # Oversold reciente en las últimas N velas (permite re-entrada aunque el cruce fuese antes)
    recent_oversold = df["rsi"].rolling(lookback_bars, min_periods=1).min() < rsi_buy

    # --- ENTRADA (dos vías, ambas requieren confirmación de tendencia) --------
    # 1) Cruce clásico en uptrend
    buy_classic = uptrend & above_sma & rsi_up_cross

    # 2) Recuperación de uptrend tras oversold reciente (más robusto en 15m)
    buy_recovery = uptrend & above_sma & recent_oversold & (df["rsi"] >= rsi_buy) & rsi_rising

    buy_condition = buy_classic | buy_recovery

    # --- SALIDA ---------------------------------------------------------------
    # Sobrecompra fuerte, pérdida de SMA con margen, o 'stop bar' si ya estamos dentro.
    stop_bar = df["close"] < df["close"].shift() * 0.98  # -2% bar
    sell_condition = (
        (df["rsi"] > rsi_sell)
        | (df["close"] < df["sma"] * 0.995)
        | (in_position & stop_bar)
    )

    # --- Señal impulsional por vela ------------------------------------------
    df["signal_raw"] = np.select([buy_condition, sell_condition], [1, -1], default=0)
    df["position"]   = df["signal_raw"]

    # --- Razón (debug amigable en logs) --------------------------------------
    df["reason"] = np.where(
        buy_classic, "BUY:uptrend&cross",
        np.where(
            buy_recovery, "BUY:uptrend&recovery",
            np.where(
                sell_condition, "SELL:rsi_high OR <sma OR stop_bar", "HOLD"
            ),
        ),
    )

    return df

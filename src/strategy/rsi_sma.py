# src/strategy/rsi_sma.py
import pandas as pd, numpy as np

def rsi_sma_strategy(
    df,
    rsi_period=14,
    sma_period=50,
    rsi_buy=30,
    rsi_sell=70,
    in_position=False,
    stop_bar_pct=0.02,
    **_,
):
    # --- Indicadores (minúsculas para coherencia con el logger) ---
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).rolling(rsi_period, min_periods=rsi_period).mean()
    loss  = (-delta.clip(upper=0)).rolling(rsi_period, min_periods=rsi_period).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    df["sma"]    = df["close"].rolling(sma_period, min_periods=sma_period).mean()
    df["ema200"] = df["close"].ewm(span=200, min_periods=200).mean()

    tr = pd.concat([
        (df["high"] - df["low"]),
        (df["high"] - df["close"].shift()).abs(),
        (df["low"]  - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    # min_periods=1 para evitar NaN perpetuo en el log de ATR%
    df["atr"]     = tr.rolling(14, min_periods=1).mean()
    df["atr_pct"] = df["atr"] / df["close"]

    # --- Reglas base ---
    uptrend  = df["close"] >= df["ema200"]
    rsi_up   = (df["rsi"].shift(1) < rsi_buy) & (df["rsi"] >= rsi_buy)        # cruce al alza
    rsi_down = (df["rsi"].shift(1) > rsi_sell) & (df["rsi"] <= rsi_sell)      # cruce a la baja

    # 1) Pullback clásico (lo que ya teníamos): cruce de RSI en uptrend
    buy_pb = uptrend & rsi_up

    # 2) Breakout de precio sobre la SMA con RSI “no flojo”
    #    (evita quedarnos fuera si el cruce de RSI ocurrió antes de que arrancara el bot)
    cross_sma = (
        (df["close"].shift(1) <= df["sma"].shift(1)) &
        (df["close"] > df["sma"] * 1.001) &
        (df["rsi"] >= rsi_buy - 5)
    )

    # 3) Momentum (continuación): RSI por encima de rsi_buy y subiendo, con precio sobre la SMA
    momentum = uptrend & (df["rsi"] >= rsi_buy) & (df["rsi"] > df["rsi"].shift(1)) & (df["close"] > df["sma"])

    # 4) Mean-reversion muy conservadora en downtrend (opcional, poco frecuente)
    mr_dt = (~uptrend) & (df["rsi"] <= min(25, rsi_buy)) & (df["close"] > df["sma"] * 1.002)

    buy_condition = buy_pb | cross_sma | momentum | mr_dt

    # Salidas: cruce de sobrecompra, pérdida de SMA con margen o vela de -2% (stop bar)
    stop_bar  = df["close"] < df["close"].shift() * (1 - float(stop_bar_pct))
    sma_break = df["close"] < df["sma"] * 0.995
    sell_condition = rsi_down | sma_break | stop_bar

    # --- Señal consumible por el bot ---
    df["signal_raw"] = np.select([buy_condition, sell_condition], [1, -1], default=0)

    # Solo emitimos venta si estamos dentro
    df["position"] = 0
    df.loc[buy_condition, "position"] = 1
    if in_position:
        df.loc[sell_condition, "position"] = -1

    # Motivo para el log
    df["reason"] = np.select(
        [buy_pb, cross_sma, momentum, mr_dt, sell_condition],
        ["BUY:pullback_rsi", "BUY:cross_sma", "BUY:momentum", "BUY:mr_downtrend", "SELL:rsi/sma/stop"],
        default="HOLD",
    )
    return df

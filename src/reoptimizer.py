# -*- coding: utf-8 -*-
"""
Reoptimizador periódico
- Recalcula RSI+SMA sobre datos recientes del símbolo/timeframe
- Escribe results/active_params_{SYMBOL}_{TF}.json con el mejor setup
- Diseñado para ejecutarse 24/7 bajo PM2
"""

import os
import json
import time
import pandas as pd
from datetime import datetime, timezone
from src.binance_api import get_historical_data
from src.strategy.rsi_sma import rsi_sma as rsi_sma_strategy  # cambia si tu función se llama distinto
from src.backtest import backtest_signals

SYMBOL     = os.getenv("REOPT_SYMBOL",    "BTCUSDC")
TIMEFRAME  = os.getenv("REOPT_TIMEFRAME", "15m")
LIMIT      = int(os.getenv("REOPT_LIMIT", "8000"))      # ~ histórico usado
EVERY_MIN  = int(os.getenv("REOPT_EVERY_MIN", "60"))    # cada cuántos minutos reoptimizar
OUT_PATH   = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"

# Espacio de búsqueda (ajústalo cuando quieras)
RSI_PERIODS     = [10, 14, 21]
SMA_PERIODS     = [20, 30, 50]
RSI_BUYS        = [30, 35, 40]
RSI_SELLS       = [60, 65, 70]

os.makedirs("results", exist_ok=True)

def _score(row):
    # Score robusto: Sharpe pondera más que retorno; penaliza drawdown
    return (row["sharpe_ratio"] * 0.6) + (row["total_return"] * 0.4) + (row["max_drawdown"] * -0.2)

def _optimize_once():
    df = get_historical_data(SYMBOL, TIMEFRAME, LIMIT).copy()

    results = []
    for rp in RSI_PERIODS:
        for sp in SMA_PERIODS:
            for b in RSI_BUYS:
                for s in RSI_SELLS:
                    if b >= s:
                        continue
                    d = df.copy()
                    d = rsi_sma_strategy(d, rsi_period=rp, sma_period=sp, rsi_buy=b, rsi_sell=s)
                    d, capital, metrics = backtest_signals(d, timeframe=TIMEFRAME)
                    results.append(dict(
                        rsi_period=rp, sma_period=sp, rsi_buy=b, rsi_sell=s,
                        total_return=round(float(metrics["total_return"] * 100), 2),   # %
                        sharpe_ratio=round(float(metrics["sharpe_ratio"]), 2),
                        max_drawdown=round(float(metrics["max_drawdown"] * 100), 2),  # %
                    ))

    if not results:
        return None

    dfres = pd.DataFrame(results)
    dfres["score"] = dfres.apply(_score, axis=1)
    best = dfres.sort_values("score", ascending=False).iloc[0]

    payload = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "data_end": str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best": {
            "strategy": "rsi_sma",
            "params": {
                "rsi_period": int(best["rsi_period"]),
                "sma_period": int(best["sma_period"]),
                "rsi_buy": int(best["rsi_buy"]),
                "rsi_sell": int(best["rsi_sell"]),
            },
            "metrics": {
                "total_return_pct": float(best["total_return"]),
                "sharpe_ratio": float(best["sharpe_ratio"]),
                "max_drawdown_pct": float(best["max_drawdown"]),
                "score": float(best["score"])
            }
        }
    }

    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, OUT_PATH)

    print(f"✅ Reopt OK {SYMBOL}/{TIMEFRAME} → {OUT_PATH}")
    print("   • Params :", payload["best"]["params"])
    print("   • Metrics:", payload["best"]["metrics"])
    return payload

def main():
    print(f"🔁 REOPT RUNNER — {SYMBOL} {TIMEFRAME}  cada {EVERY_MIN}m  (limit={LIMIT})")
    while True:
        try:
            _optimize_once()
        except Exception as e:
            print(f"❌ Reopt error: {e}")
        time.sleep(EVERY_MIN * 60)

if __name__ == "__main__":
    main()

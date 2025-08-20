# -*- coding: utf-8 -*-
"""
Reoptimizer “suave” para PM2:
- Cada ciclo lee results/rsi_optimization_{TF}.csv
- Escribe results/active_params_{SYMBOL}_{TF}.json con el mejor set
- NO crashea si no hay CSV: espera y reintenta
- Diseñado para ejecutarse indefinidamente bajo PM2 (sin reinicios)
"""

import os
import time
import json
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

SYMBOL    = os.getenv("TRADING_SYMBOL", "BTCUSDC")
TIMEFRAME = os.getenv("TRADING_TIMEFRAME", "15m")
SLEEP_SECONDS = int(os.getenv("REOPT_SLEEP_SECONDS", "900"))  # 15 min

OPT_CSV   = f"results/rsi_optimization_{TIMEFRAME}.csv"
ACTIVE_JSON = f"results/active_params_{SYMBOL}_{TIMEFRAME}.json"

def pick_best_from_csv(path: str):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    for c in ["total_return","sharpe_ratio","max_drawdown"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["total_return"])
    if df.empty:
        return None
    best = df.sort_values("total_return", ascending=False).iloc[0]
    params = dict(
        rsi_period=int(best["rsi_period"]),
        sma_period=int(best["sma_period"]),
        rsi_buy=int(best["rsi_buy"]),
        rsi_sell=int(best["rsi_sell"]),
    )
    metrics = dict(
        total_return=float(best["total_return"]),
        sharpe_ratio=float(best["sharpe_ratio"]),
        max_drawdown=float(best["max_drawdown"]),
    )
    payload = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "data_end": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best": {
            "strategy": "rsi_sma",
            "params": params,
            "metrics": {
                "total_return_pct": metrics["total_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown_pct": metrics["max_drawdown"],
            },
        },
    }
    return payload

def main_loop():
    print(f"🔁 Reoptimizer activo para {SYMBOL} {TIMEFRAME}. Fuente CSV: {OPT_CSV}")
    last_written = None

    while True:
        try:
            best = pick_best_from_csv(OPT_CSV)
            if best is None:
                print(f"⏳ No hay CSV o sin datos válidos aún: {OPT_CSV}")
            else:
                os.makedirs("results", exist_ok=True)
                # Evita escrituras innecesarias
                blob = json.dumps(best, sort_keys=True)
                if blob != last_written:
                    with open(ACTIVE_JSON, "w") as f:
                        f.write(blob)
                    last_written = blob
                    print(f"✅ Actualizado {ACTIVE_JSON} → {best['best']['params']}")
                else:
                    print("👍 Sin cambios en el mejor set, no se reescribe.")
        except Exception as e:
            print(f"⚠️ Reoptimizer warning: {e}")

        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main_loop()

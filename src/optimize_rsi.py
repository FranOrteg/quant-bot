# src/optimize_rsi.py
# Optimización de RSI+SMA con CLI consistente con el bot en vivo.
# - Acepta --symbol (TRADING_SYMBOL o par ccxt)
# - Acepta --timeframe
# - Guarda CSV en results/rsi_optimization_<TF>.csv
# - Exporta best_params a results/best_rsi_<TF>.json

import os
import argparse
import json
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt

from src.binance_api import get_historical_data
from src.strategy.rsi_sma import rsi_sma_strategy
from src.backtest import backtest_signals

def to_ccxt_symbol(sym: str) -> str:
    """Convierte 'BTCUSDC' → 'BTC/USDC' si no trae barra."""
    if "/" in sym:
        return sym
    QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "TUSD", "BTC", "ETH", "EUR", "TRY")
    for q in QUOTES:
        if sym.endswith(q):
            base = sym[:-len(q)]
            return f"{base}/{q}"
    return sym

def parse_args():
    parser = argparse.ArgumentParser(description="Grid search RSI+SMA")
    parser.add_argument("--symbol", default=os.getenv("TRADING_SYMBOL", "BTCUSDC"),
                        help="Símbolo (BTCUSDC o BTC/USDT). Se normaliza a ccxt internamente.")
    parser.add_argument("--timeframe", default="1h", help="TF (5m, 15m, 1h, ...)")
    parser.add_argument("--limit", type=int, default=8000, help="Nº de velas a descargar")
    parser.add_argument("--plot", action="store_true", help="Guardar gráfico del top-5")
    return parser.parse_args()

def main():
    args = parse_args()
    os.makedirs("results", exist_ok=True)

    symbol_ccxt = to_ccxt_symbol(args.symbol)

    # === Datos (mismo loader que el bot) ===
    df = get_historical_data(symbol_ccxt, args.timeframe, args.limit).copy()
    if df.empty:
        raise RuntimeError(f"No se obtuvieron datos para {symbol_ccxt} {args.timeframe}")

    data_end = pd.to_datetime(df["timestamp"].iloc[-1])

    # === Rango de parámetros ===
    rsi_periods     = [5, 10, 14, 21]
    sma_periods     = [10, 15, 20, 30]
    rsi_buy_levels  = [30, 35, 40]
    rsi_sell_levels = [60, 65, 70]

    rows = []
    for rsi_p in rsi_periods:
        for sma_p in sma_periods:
            for rsi_buy in rsi_buy_levels:
                for rsi_sell in rsi_sell_levels:
                    if rsi_buy >= rsi_sell:
                        continue

                    df_copy = df.copy()
                    df_copy = rsi_sma_strategy(
                        df_copy,
                        rsi_period=rsi_p,
                        sma_period=sma_p,
                        rsi_buy=rsi_buy,
                        rsi_sell=rsi_sell
                    )
                    df_bt, capital, metrics = backtest_signals(df_copy, timeframe=args.timeframe)

                    rows.append({
                        "strategy": "rsi_sma",
                        "rsi_period": rsi_p,
                        "sma_period": sma_p,
                        "rsi_buy": rsi_buy,
                        "rsi_sell": rsi_sell,
                        "capital_final": round(capital, 2),
                        "total_return": round(metrics["total_return"] * 100, 2),
                        "sharpe_ratio": round(metrics["sharpe_ratio"], 2),
                        "max_drawdown": round(metrics["max_drawdown"] * 100, 2),
                        "timestamp": datetime.utcnow().isoformat()
                    })

    results_df = pd.DataFrame(rows)
    out_csv = f"results/rsi_optimization_{args.timeframe}.csv"
    results_df.to_csv(out_csv, index=False)

    # Top 5 y best
    top5 = results_df.sort_values("total_return", ascending=False).head(5)
    print("\n📈 Top 5 configuraciones RSI + SMA por retorno total:")
    print(top5.to_string(index=False))

    best_row = top5.iloc[0].to_dict()
    best_payload = {
        "symbol": symbol_ccxt,
        "timeframe": args.timeframe,
        "data_end": data_end.isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
        "best": {
            "strategy": "rsi_sma",
            "params": {
                "rsi_period": int(best_row["rsi_period"]),
                "sma_period": int(best_row["sma_period"]),
                "rsi_buy": int(best_row["rsi_buy"]),
                "rsi_sell": int(best_row["rsi_sell"]),
            },
            "metrics": {
                "total_return_pct": float(best_row["total_return"]),
                "sharpe_ratio": float(best_row["sharpe_ratio"]),
                "max_drawdown_pct": float(best_row["max_drawdown"]),
            }
        }
    }
    best_json = f"results/best_rsi_{args.timeframe}.json"
    with open(best_json, "w") as f:
        json.dump(best_payload, f, indent=2)
    print(f"\n✅ Best set guardado en: {best_json}")
    print(f"✅ CSV de resultados:   {out_csv}")

    if args.plot:
        plt.figure(figsize=(10, 5))
        plt.bar(top5.index.astype(str), top5["total_return"])
        plt.title(f"Top 5 RSI+SMA ({symbol_ccxt} {args.timeframe})")
        plt.ylabel("Retorno (%)")
        plt.xlabel("Setup (fila)")
        for i, row in top5.iterrows():
            label = f"{int(row['rsi_period'])}/{int(row['sma_period'])} | {int(row['rsi_buy'])}-{int(row['rsi_sell'])}"
            plt.text(i, row["total_return"] + 0.1, label, ha="center", fontsize=8, rotation=45)
        plt.tight_layout()
        plot_path = f"results/rsi_top5_{args.timeframe}.png"
        plt.savefig(plot_path)
        print(f"📊 Gráfico guardado en: {plot_path}")

if __name__ == "__main__":
    main()

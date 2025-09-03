# src/optimize_rsi.py
# -*- coding: utf-8 -*-
# Optimización de RSI+SMA con grid que incluye lookback_bars.
# - Acepta --symbol / --timeframe / --limit / --plot / --write-active
# - Lee grids desde ENV o CLI
# - Guarda CSV en results/rsi_optimization_<TF>.csv
# - Exporta best_params en results/best_rsi_<TF>.json (con metadata)
# - Usa el mismo loader de datos que el bot y la misma estrategia viva

import os
import argparse
import json
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt

from src.binance_api import get_historical_data
from src.strategy.rsi_sma import rsi_sma_strategy
from src.backtest import backtest_signals

# ---------- helpers de parsing ----------

def _parse_int_list(text: str, default: list[int]) -> list[int]:
    if text is None:
        return default
    out = []
    for tok in str(text).split(","):
        tok = tok.strip()
        if tok and tok.lstrip("-").isdigit():
            out.append(int(tok))
    return out or default

def _env_list(name: str, default: list[int]) -> list[int]:
    return _parse_int_list(os.getenv(name, ""), default)

def _no_slash_symbol(sym: str) -> str:
    return sym.replace("/", "")

# ---------- CLI ----------

def parse_args():
    parser = argparse.ArgumentParser(description="Grid search RSI+SMA (+ lookback_bars)")
    parser.add_argument("--symbol", default=os.getenv("TRADING_SYMBOL", "BTCUSDC"),
                        help="Símbolo (ej: BTCUSDC o BTC/USDT)")
    parser.add_argument("--timeframe", default=os.getenv("TRADING_TIMEFRAME", "1h"),
                        help="TF (ej: 5m, 15m, 1h)")
    parser.add_argument("--limit", type=int, default=int(os.getenv("REOPT_LIMIT", "8000")),
                        help="Nº de velas a descargar")
    parser.add_argument("--plot", action="store_true", help="Guardar gráfico del top-5")

    # grids por CLI (opcionales); si no se pasan, se usan ENV o defaults
    parser.add_argument("--rsi", help='RSI_PERIODS (ej "5,10,14,21")')
    parser.add_argument("--sma", help='SMA_PERIODS (ej "10,15,20,30")')
    parser.add_argument("--buy", help='RSI_BUY_LEVELS (ej "30,35,40")')
    parser.add_argument("--sell", help='RSI_SELL_LEVELS (ej "60,65,70")')
    parser.add_argument("--lb", help='RSI_LOOKBACK_GRID (ej "6,8,12")')

    # opcional: escribir active_params_<SYMBOL>_<TF>.json directamente
    parser.add_argument("--write-active", action="store_true",
                        help="Escribe results/active_params_<SYMBOL>_<TF>.json con el BEST set")
    return parser.parse_args()

# ---------- Gate (solo para imprimir resumen informativo) ----------
def _gate_env():
    min_ret = float(os.getenv("REOPT_MIN_RETURN_PCT", "0.0"))
    min_shp = float(os.getenv("REOPT_MIN_SHARPE", "0.0"))
    max_dd  = float(os.getenv("REOPT_MAX_DD_PCT", "20.0"))
    return min_ret, min_shp, max_dd

# ---------- main ----------

def main():
    args = parse_args()
    os.makedirs("results", exist_ok=True)

    # Grids: prioridad CLI > ENV > defaults
    rsi_periods     = _parse_int_list(args.rsi,  _env_list("RSI_PERIODS",        [5, 10, 14, 21]))
    sma_periods     = _parse_int_list(args.sma,  _env_list("SMA_PERIODS",        [10, 15, 20, 30]))
    rsi_buy_levels  = _parse_int_list(args.buy,  _env_list("RSI_BUY_LEVELS",     [30, 35, 40]))
    rsi_sell_levels = _parse_int_list(args.sell, _env_list("RSI_SELL_LEVELS",    [60, 65, 70]))
    lb_values       = _parse_int_list(args.lb,   _env_list("RSI_LOOKBACK_GRID",  [6, 8, 12]))

    # === Descarga de datos ===
    df = get_historical_data(args.symbol, args.timeframe, args.limit).copy()
    if df.empty:
        raise RuntimeError(f"No se obtuvieron datos para {args.symbol} {args.timeframe}")

    # Limpieza ligera por si hubiese huecos/duplicados
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = (
        df.dropna(subset=["timestamp"])
          .sort_values("timestamp")
          .drop_duplicates(subset=["timestamp"], keep="last")
          .reset_index(drop=True)
    )

    data_end = pd.to_datetime(df["timestamp"].iloc[-1])

    # === Grid search ===
    results = []
    total_loops = len(rsi_periods) * len(sma_periods) * len(rsi_buy_levels) * len(rsi_sell_levels) * len(lb_values)
    print(f"▶️ Grid total: {total_loops} combinaciones "
          f"(RSI={rsi_periods} | SMA={sma_periods} | BUY={rsi_buy_levels} | SELL={rsi_sell_levels} | LB={lb_values})")

    loops = 0
    for rsi_p in rsi_periods:
        for sma_p in sma_periods:
            for rsi_buy in rsi_buy_levels:
                for rsi_sell in rsi_sell_levels:
                    if rsi_buy >= rsi_sell:
                        continue
                    for lb in lb_values:
                        loops += 1
                        df_copy = df.copy()
                        df_copy = rsi_sma_strategy(
                            df_copy,
                            rsi_period=rsi_p,
                            sma_period=sma_p,
                            rsi_buy=rsi_buy,
                            rsi_sell=rsi_sell,
                            lookback_bars=lb,
                        )
                        df_bt, capital, metrics = backtest_signals(df_copy, timeframe=args.timeframe)

                        results.append({
                            "strategy": "rsi_sma",
                            "rsi_period": rsi_p,
                            "sma_period": sma_p,
                            "rsi_buy": rsi_buy,
                            "rsi_sell": rsi_sell,
                            "lookback_bars": lb,
                            "capital_final": round(capital, 2),
                            "total_return": round(metrics["total_return"] * 100, 2),
                            "sharpe_ratio": round(metrics["sharpe_ratio"], 2),
                            "max_drawdown": round(metrics["max_drawdown"] * 100, 2),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        if loops % 50 == 0:
                            print(f"  …{loops}/{total_loops} combinaciones evaluadas")

    results_df = pd.DataFrame(results)
    out_csv = f"results/rsi_optimization_{args.timeframe}.csv"
    results_df.to_csv(out_csv, index=False)

    # Top 5 por retorno
    top5 = results_df.sort_values("total_return", ascending=False).head(5)
    print("\n📈 Top 5 configuraciones RSI + SMA (+LB) por retorno total:")
    print(top5.to_string(index=False))

    # Resumen de gate (informativo)
    g_min_ret, g_min_shp, g_max_dd = _gate_env()
    passed = results_df[
        (results_df["total_return"] >= g_min_ret) &
        (results_df["sharpe_ratio"] >= g_min_shp) &
        (results_df["max_drawdown"] >= -abs(g_max_dd))
    ]
    print(f"\n🔎 Gate info (min_ret={g_min_ret}%, min_sharpe={g_min_shp}, maxDD=-{abs(g_max_dd)}%): "
          f"{len(passed)}/{len(results_df)} filas pasan")

    # Best (por retorno, sin aplicar gate aquí; el gate lo aplicará el reoptimizer)
    best_row = top5.iloc[0].to_dict()
    best_payload = {
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "data_end": data_end.isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
        "best": {
            "params": {
                "rsi_period": int(best_row["rsi_period"]),
                "sma_period": int(best_row["sma_period"]),
                "rsi_buy": int(best_row["rsi_buy"]),
                "rsi_sell": int(best_row["rsi_sell"]),
                "lookback_bars": int(best_row.get("lookback_bars", 0)),
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

    # (Opcional) escribir active_params_<SYMBOL>_<TF>.json directamente
    if args.write_active:
        sym_noslash = _no_slash_symbol(args.symbol)
        active_json = f"results/active_params_{sym_noslash}_{args.timeframe}.json"
        with open(active_json, "w") as f:
            f.write(json.dumps({
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "generated_at": datetime.utcnow().isoformat(),
                "best": {
                    "strategy": "rsi_sma",
                    "params": best_payload["best"]["params"],
                    "metrics": best_payload["best"]["metrics"],
                }
            }, sort_keys=True, separators=(",", ":")))
        print(f"📝 ACTIVE escrito (forzado): {active_json}")

    # Plot
    if args.plot:
        plt.figure(figsize=(10, 5))
        plt.bar(top5.index.astype(str), top5["total_return"])
        plt.title(f"Top 5 RSI+SMA+LB ({args.symbol} {args.timeframe})")
        plt.ylabel("Retorno (%)")
        plt.xlabel("Fila en CSV")
        for i, row in top5.iterrows():
            label = f"RSI{int(row['rsi_period'])}/SMA{int(row['sma_period'])} | {int(row['rsi_buy'])}-{int(row['rsi_sell'])} | LB{int(row['lookback_bars'])}"
            plt.text(i, row["total_return"] + 0.1, label, ha="center", fontsize=8, rotation=45)
        # margen inferior para que quepan etiquetas
        plt.gcf().subplots_adjust(bottom=0.25)
        plt.tight_layout()
        plot_path = f"results/rsi_top5_{args.timeframe}.png"
        plt.savefig(plot_path)
        print(f"📊 Gráfico guardado en: {plot_path}")

if __name__ == "__main__":
    main()

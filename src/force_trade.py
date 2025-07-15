import sys
from src.paper_trading import buy, sell, get_price
from src.strategy_selector import select_best_strategy

def main():
    if len(sys.argv) < 2:
        print("❌ Uso: python3 -m src.force_trade [buy|sell] [opcional:precio]")
        sys.exit(1)

    action = sys.argv[1].upper()
    price = float(sys.argv[2]) if len(sys.argv) > 2 else get_price()

    symbol = "BTCUSDC"  # Cambia aquí si quieres otro símbolo
    strategy_name, _, params, _ = select_best_strategy()

    if action == "BUY":
        buy(symbol, price, strategy_name, params)
        print(f"✅ Señal BUY forzada ejecutada con precio {price}")
    elif action == "SELL":
        sell(symbol, price, strategy_name, params)
        print(f"✅ Señal SELL forzada ejecutada con precio {price}")
    else:
        print("❌ Acción no válida. Usa 'buy' o 'sell'")

if __name__ == "__main__":
    main()

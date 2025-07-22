# src/risk_management.py
import pandas as pd
import numpy as np

class DynamicRiskManager:
    def __init__(self, initial_capital=10000, max_risk_per_trade=0.02, 
                 max_portfolio_risk=0.15, atr_period=14):
        self.initial_capital = initial_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.max_portfolio_risk = max_portfolio_risk
        self.atr_period = atr_period
        
    def calculate_atr(self, df):
        """Calcular Average True Range para volatilidad"""
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_close'] = abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['ATR'] = df['true_range'].rolling(window=self.atr_period).mean()
        return df
    
    def calculate_position_size(self, df, signal_strength=1.0):
        """
        Calcular tamaño de posición basado en:
        - Volatilidad (ATR)
        - Fuerza de la señal
        - Capital disponible
        - Máximo riesgo permitido
        """
        df = self.calculate_atr(df)
        
        # Stop loss dinámico basado en ATR
        df['stop_loss_distance'] = df['ATR'] * 2.0  # 2x ATR como stop loss
        
        # Calcular position size para riskar max_risk_per_trade del capital
        df['position_size'] = (
            (self.initial_capital * self.max_risk_per_trade) / 
            df['stop_loss_distance']
        ) * signal_strength
        
        # Limitar position size al 20% del capital
        max_position_value = self.initial_capital * 0.2
        df['position_size'] = np.minimum(
            df['position_size'], 
            max_position_value / df['close']
        )
        
        return df
    
    def dynamic_stop_loss(self, df, entry_price, position_type='long'):
        """
        Stop loss que se ajusta con la volatilidad y trailing
        """
        df = self.calculate_atr(df)
        
        if position_type == 'long':
            # Stop loss inicial
            initial_stop = entry_price - (df['ATR'].iloc[-1] * 2)
            
            # Trailing stop basado en ATR
            df['trailing_stop'] = df['close'] - (df['ATR'] * 1.5)
            
            # El stop loss nunca baja, solo sube
            df['dynamic_stop'] = df['trailing_stop'].cummax()
            df['dynamic_stop'].iloc[0] = initial_stop
            
        else:  # short
            initial_stop = entry_price + (df['ATR'].iloc[-1] * 2)
            df['trailing_stop'] = df['close'] + (df['ATR'] * 1.5)
            df['dynamic_stop'] = df['trailing_stop'].cummin()
            df['dynamic_stop'].iloc[0] = initial_stop
            
        return df

def enhanced_backtest_with_risk_management(df, initial_capital=10000, timeframe="1h"):
    """
    Backtest mejorado con gestión de riesgo dinámica
    """
    risk_manager = DynamicRiskManager(initial_capital)
    
    capital = initial_capital
    position = 0
    entry_price = 0
    position_size = 0
    equity_curve = []
    trades_log = []
    
    FEE = 0.00075
    SLIPPAGE = 0.0004
    
    # Calcular ATR y position sizes
    df = risk_manager.calculate_atr(df)
    
    for i, row in df.iterrows():
        price = row['close']
        signal = row['position']
        signal_strength = row.get('signal_strength', 1.0)
        
        # Salir por stop loss
        if position != 0:
            if position > 0:  # Long position
                stop_price = entry_price - (row['ATR'] * 2)
                if price <= stop_price:
                    # Stop loss hit
                    exit_price = stop_price * (1 - SLIPPAGE)
                    pnl = (exit_price - entry_price) / entry_price
                    capital *= (1 + pnl * position_size) * (1 - FEE)
                    
                    trades_log.append({
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'reason': 'stop_loss',
                        'position_size': position_size
                    })
                    
                    position = 0
                    position_size = 0
            
            elif position < 0:  # Short position
                stop_price = entry_price + (row['ATR'] * 2)
                if price >= stop_price:
                    exit_price = stop_price * (1 + SLIPPAGE)
                    pnl = (entry_price - exit_price) / entry_price
                    capital *= (1 + pnl * abs(position_size)) * (1 - FEE)
                    
                    trades_log.append({
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'reason': 'stop_loss',
                        'position_size': abs(position_size)
                    })
                    
                    position = 0
                    position_size = 0
        
        # Nuevas señales
        if signal == 1 and position == 0:  # BUY
            entry_price = price * (1 + SLIPPAGE)
            
            # Calcular position size dinámico
            stop_distance = row['ATR'] * 2
            risk_amount = capital * risk_manager.max_risk_per_trade
            position_size = min(
                (risk_amount / stop_distance) * signal_strength,
                (capital * 0.2) / entry_price  # Max 20% of capital
            )
            
            position = 1
            capital *= (1 - FEE)
            
        elif signal == -1 and position == 1:  # SELL
            exit_price = price * (1 - SLIPPAGE)
            pnl = (exit_price - entry_price) / entry_price
            capital *= (1 + pnl * position_size) * (1 - FEE)
            
            trades_log.append({
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'reason': 'signal',
                'position_size': position_size
            })
            
            position = 0
            position_size = 0
        
        equity_curve.append(capital)
    
    df['equity'] = equity_curve
    df['returns'] = df['equity'].pct_change().fillna(0)
    
    # Métricas mejoradas
    mean_r = df['returns'].mean()
    std_r = df['returns'].std()
    
    ANNUALIZATION = {
        "1d": 252, "4h": 24*365/4, "1h": 24*365,
        "30m": 24*2*365, "15m": 24*4*365, "5m": 24*12*365
    }
    
    ann_factor = ANNUALIZATION.get(timeframe, 252)
    sharpe_ratio = 0 if std_r == 0 else mean_r / std_r * np.sqrt(ann_factor)
    
    rolling_max = df['equity'].cummax()
    max_drawdown = ((df['equity'] - rolling_max) / rolling_max).min()
    total_return = df['equity'].iloc[-1] / initial_capital - 1
    
    # Métricas adicionales
    trades_df = pd.DataFrame(trades_log)
    
    if len(trades_df) > 0:
        win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df)
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] > 0]) > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] < 0]) > 0 else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf') if avg_win > 0 else 0
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
    
    metrics = {
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_trades': len(trades_df),
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }
    
    return df, capital, metrics, trades_df

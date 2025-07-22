# src/ml_strategy.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import StandardScaler
import joblib
import os

class MLTradingStrategy:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        
    def create_features(self, df):
        """
        Crear características técnicas para el modelo ML
        """
        df = df.copy()
        
        # Indicadores técnicos básicos
        df['returns'] = df['close'].pct_change()
        df['returns_2'] = df['close'].pct_change(2)
        df['returns_5'] = df['close'].pct_change(5)
        
        # MACD
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Volatilidad
        df['volatility'] = df['returns'].rolling(window=20).std()
        df['atr'] = self.calculate_atr(df)
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Price patterns
        df['high_low_ratio'] = df['high'] / df['low']
        df['close_open_ratio'] = df['close'] / df['open']
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
            df[f'price_sma_{period}_ratio'] = df['close'] / df[f'sma_{period}']
        
        # Momentum indicators
        df['momentum_5'] = df['close'] / df['close'].shift(5)
        df['momentum_10'] = df['close'] / df['close'].shift(10)
        
        # Rate of Change
        df['roc_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
        df['roc_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100
        
        return df
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        return true_range.rolling(window=period).mean()
    
    def create_labels(self, df, forward_periods=5, threshold=0.02):
        """
        Crear etiquetas para el modelo:
        1: Compra (precio subirá más del threshold en forward_periods)
        -1: Venta (precio bajará más del threshold en forward_periods)  
        0: Hold (cambio menor al threshold)
        """
        df = df.copy()
        
        # Calcular el retorno futuro
        df['future_return'] = df['close'].shift(-forward_periods) / df['close'] - 1
        
        # Crear etiquetas
        df['label'] = 0  # Hold
        df.loc[df['future_return'] > threshold, 'label'] = 1    # Buy
        df.loc[df['future_return'] < -threshold, 'label'] = -1  # Sell
        
        return df
    
    def prepare_data(self, df):
        """
        Preparar datos para entrenamiento
        """
        # Crear características y etiquetas
        df = self.create_features(df)
        df = self.create_labels(df)
        
        # Seleccionar características
        feature_cols = [
            'returns', 'returns_2', 'returns_5', 'macd', 'macd_signal', 'macd_hist',
            'rsi', 'bb_position', 'volatility', 'atr', 'volume_ratio',
            'high_low_ratio', 'close_open_ratio', 'momentum_5', 'momentum_10',
            'roc_5', 'roc_10'
        ]
        
        # Añadir ratios de SMA
        for period in [5, 10, 20, 50]:
            feature_cols.append(f'price_sma_{period}_ratio')
        
        self.feature_names = feature_cols
        
        # Limpiar datos
        df = df.dropna()
        
        X = df[feature_cols]
        y = df['label']
        
        return X, y, df
    
    def train_model(self, df, test_size=0.2):
        """
        Entrenar modelo con validación temporal
        """
        X, y, df_clean = self.prepare_data(df)
        
        # División temporal (importante para series de tiempo)
        split_index = int(len(X) * (1 - test_size))
        X_train, X_test = X[:split_index], X[split_index:]
        y_train, y_test = y[:split_index], y[split_index:]
        
        print(f"📊 Datos de entrenamiento: {len(X_train)} muestras")
        print(f"📊 Datos de prueba: {len(X_test)} muestras")
        
        # Escalar características
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Entrenar modelo Random Forest
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced'  # Para manejar clases desbalanceadas
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluar modelo
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"🎯 Precisión del modelo: {accuracy:.3f}")
        print("\n📈 Reporte de clasificación:")
        print(classification_report(y_test, y_pred))
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\n🔝 Top 10 características más importantes:")
        print(feature_importance.head(10).to_string(index=False))
        
        return accuracy, feature_importance
    
    def predict_signals(self, df):
        """
        Generar señales de trading usando el modelo entrenado
        """
        if self.model is None:
            raise ValueError("Modelo no entrenado. Usar train_model() primero.")
        
        # Crear características
        df = self.create_features(df)
        
        # Preparar datos para predicción
        X = df[self.feature_names].fillna(0)  # Rellenar NaN con 0
        X_scaled = self.scaler.transform(X)
        
        # Predecir
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        # Añadir predicciones al dataframe
        df['ml_signal'] = predictions
        
        # Añadir probabilidades (confianza de la señal)
        df['ml_confidence'] = np.max(probabilities, axis=1)
        
        # Convertir a formato compatible con backtesting
        df['position'] = 0
        df.loc[df['ml_signal'] == 1, 'position'] = 1   # Buy
        df.loc[df['ml_signal'] == -1, 'position'] = -1  # Sell
        
        # Usar solo señales con alta confianza
        confidence_threshold = 0.6
        df.loc[df['ml_confidence'] < confidence_threshold, 'position'] = 0
        
        return df
    
    def save_model(self, filepath='models/ml_trading_model.pkl'):
        """Guardar modelo entrenado"""
        os.makedirs('models', exist_ok=True)
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }
        joblib.dump(model_data, filepath)
        print(f"💾 Modelo guardado en {filepath}")
    
    def load_model(self, filepath='models/ml_trading_model.pkl'):
        """Cargar modelo entrenado"""
        if os.path.exists(filepath):
            model_data = joblib.load(filepath)
            self.model = model_data['model']
            self.scaler = model_data['scaler'] 
            self.feature_names = model_data['feature_names']
            print(f"📂 Modelo cargado desde {filepath}")
            return True
        else:
            print(f"❌ No se encontró modelo en {filepath}")
            return False

def ml_strategy_backtest():
    """
    Función para probar la estrategia ML
    """
    from src.binance_api import get_historical_data
    from src.risk_management import enhanced_backtest_with_risk_management
    
    print("🤖 INICIANDO ESTRATEGIA MACHINE LEARNING")
    print("=" * 50)
    
    # Obtener datos
    print("📊 Obteniendo datos históricos...")
    df = get_historical_data(symbol='BTC/USDT', timeframe='1h', limit=2000)
    
    # Crear y entrenar modelo
    ml_strategy = MLTradingStrategy()
    accuracy, feature_importance = ml_strategy.train_model(df)
    
    # Generar señales en datos de prueba (últimos 20%)
    split_index = int(len(df) * 0.8)
    test_df = df[split_index:].copy()
    
    test_df = ml_strategy.predict_signals(test_df)
    
    # Backtest
    print("\n💰 Ejecutando backtest...")
    df_result, capital, metrics, trades_df = enhanced_backtest_with_risk_management(test_df)
    
    print(f"\n🎯 RESULTADOS DEL BACKTEST ML:")
    print(f"Capital final: ${capital:,.2f}")
    print(f"Retorno total: {metrics['total_return']*100:.2f}%")
    print(f"Sharpe ratio: {metrics['sharpe_ratio']:.3f}")
    print(f"Máximo drawdown: {metrics['max_drawdown']*100:.2f}%")
    print(f"Win rate: {metrics['win_rate']*100:.1f}%")
    print(f"Profit factor: {metrics['profit_factor']:.2f}")
    print(f"Total trades: {metrics['total_trades']}")
    
    # Guardar modelo
    ml_strategy.save_model()
    
    # Guardar resultados
    os.makedirs('results', exist_ok=True)
    feature_importance.to_csv('results/ml_feature_importance.csv', index=False)
    
    return ml_strategy, metrics

if __name__ == "__main__":
    ml_strategy, metrics = ml_strategy_backtest()

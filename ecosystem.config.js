module.exports = {
  apps: [
    {
      name: 'quant-bot',
      script: '.venv/bin/python',
      args: '-m src.live_trader',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot',
        TRADING_SYMBOL: 'BTCUSDC',
        TRADING_TIMEFRAME: '15m',
        USE_REAL_TRADING: 'True',
        USE_REAL_BALANCE: 'True',
        USE_BINANCE_TESTNET: 'False'
      }
    },
    {
      name: 'quant-bot-5m',
      script: '.venv/bin/python',
      args: '-m src.live_trader_5m',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot',
        TRADING_SYMBOL: 'BTCUSDC',
        TRADING_TIMEFRAME: '5m',
        USE_REAL_TRADING: 'True',
        USE_REAL_BALANCE: 'True',
        USE_BINANCE_TESTNET: 'False'
      }
    },
    {
      name: 'reopt-15m',
      script: '.venv/bin/python',
      args: '-m src.reoptimizer',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      // PM2 runtime hardening
      watch: false,
      autorestart: true,
      min_uptime: '30s',
      max_restarts: 10,
      exp_backoff_restart_delay: 1000,
      kill_timeout: 5000,
      time: true,
      out_file: 'logs/pm2/reopt-15m.out.log',
      error_file: 'logs/pm2/reopt-15m.err.log',
      env: {
        TZ: 'UTC',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot',

        // === Reoptimizer target ===
        TRADING_SYMBOL: 'BTCUSDC',
        TRADING_TIMEFRAME: '15m',

        // === Frecuencia / frescura ===
        REOPT_EVERY_MIN: '15',          // objetivo lógico
        REOPT_SLEEP_SECONDS: '900',     // 15 min exactos entre ciclos
        REOPT_CSV_STALE_MIN: '60',      // si el CSV es más viejo de 60', reoptimiza
        REOPT_LIMIT: '8000',            // velas para la optimización
        REOPT_FORCE: 'False',           // pon a 'True' si quieres forzar un ciclo

        // === Quality gate ===
        REOPT_MIN_RETURN_PCT: '0',      // exige retorno >= 0% (ajústalo si quieres)
        REOPT_MIN_SHARPE: '0',          // exige Sharpe >= 0
        REOPT_MAX_DD_PCT: '20',
        REOPT_ALLOW_ABS_FALLBACK: 'True',

        // === Promociona solo si mejora (nuevo) ===
        REOPT_ONLY_IF_BETTER: 'True',
        REOPT_MIN_IMPROVE_RET: '0.25',      // mejora mínima en retorno (%) para promover
        REOPT_MIN_IMPROVE_SHARPE: '0.15',   // mejora mínima en Sharpe para promover

        // === (Opcional) Controlar tamaño del grid desde ENV (optimize_rsi) ===
        // RSI_PERIODS: '5,10,14,21',
        // SMA_PERIODS: '10,15,20,30',
        // RSI_BUY_LEVELS: '30,35,40',
        // RSI_SELL_LEVELS: '60,65,70',
        // RSI_LOOKBACK_GRID: '6,8,12',

        // === Intérprete del subproceso ===
        PYTHON_BIN: '/home/ubuntu/quant-bot/.venv/bin/python'
      }
    },
    {
      name: 'report-gen',
      script: '.venv/bin/python',
      args: '-m src.report_scheduler',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot'
      }
    },
    {
      name: 'dashboard',
      script: '.venv/bin/python',
      args: '-m src.web_dashboard',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        FLASK_ENV: 'development',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot'
      }
    }
  ]
}

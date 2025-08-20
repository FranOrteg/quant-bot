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
        USE_REAL_TRADING: 'True',
        USE_REAL_BALANCE: 'True'
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
        PYTHONPATH: '/home/ubuntu/quant-bot',
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
        PYTHONPATH: '/home/ubuntu/quant-bot',
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
      }
    },
    {
      name: 'reopt-15m',
      script: '.venv/bin/python',
      args: '-m src.reoptimizer',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot',

        // Lo que realmente lee reoptimizer.py:
        TRADING_SYMBOL: 'BTCUSDC',
        TRADING_TIMEFRAME: '15m',

        // Frecuencia del loop (en minutos) y stale del CSV (minutos):
        REOPT_EVERY_MIN: '15',          // cada 15 min
        REOPT_CSV_STALE_MIN: '60',      // si el CSV tiene ≥60 min, re-optimiza

        // Límite de velas para la optimización:
        REOPT_LIMIT: '8000'
      }
    }

  ]
}

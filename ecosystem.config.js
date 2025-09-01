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
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/home/ubuntu/quant-bot',
        TRADING_SYMBOL: 'BTCUSDC',
        TRADING_TIMEFRAME: '15m',
        REOPT_EVERY_MIN: '15',
        REOPT_CSV_STALE_MIN: '60',
        REOPT_LIMIT: '8000'
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

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
        REOPT_SYMBOL: 'BTCUSDC',
        REOPT_TIMEFRAME: '15m',
        REOPT_LIMIT: '8000',
        REOPT_EVERY_MIN: '60'
      }
    }
  ]
}

// ecosystem_5m.config.js
module.exports = {
  apps: [
    {
      name: 'quant-bot-5m',
      script: '.venv/bin/python',
      args: '-m src.live_trader_5m',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
      }
    }
  ]
}

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
      }
    }
  ]
};

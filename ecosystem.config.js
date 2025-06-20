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
    },
    {
      name: 'report-gen',
      script: '.venv/bin/python',
      args: '-m src.report_scheduler',
      cwd: '/home/ubuntu/quant-bot',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
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
      }
    }
  ]
}

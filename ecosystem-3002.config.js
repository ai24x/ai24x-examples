module.exports = {
  apps: [{
    name: 'ai24x-3002',
    script: 'server-clean-fixed.js',
    cwd: 'C:/claw/bak/daily/20260324/ai24x-website',
    args: '3002',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '200M',
    env: {
      NODE_ENV: 'production',
      PORT: 3002
    },
    error_file: 'logs/error-3002.log',
    out_file: 'logs/out-3002.log',
    log_file: 'logs/combined-3002.log',
    time: true
  }]
};
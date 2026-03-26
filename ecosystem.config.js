// PM2生态系统配置文件
module.exports = {
  apps: [{
    name: 'ai24x',
    script: 'server-permanent.js',
    cwd: __dirname,
    
    // 实例数
    instances: 1,
    exec_mode: 'fork',
    
    // 环境变量
    env: {
      NODE_ENV: 'production',
      PORT: 3000
    },
    
    // 日志配置
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    error_file: 'logs/error.log',
    out_file: 'logs/out.log',
    
    // 监控和重启
    watch: false,
    ignore_watch: [
      'node_modules',
      'logs',
      '*.log',
      '.git'
    ],
    
    // 内存和重启策略
    max_memory_restart: '200M',
    min_uptime: '10s',
    max_restarts: 10,
    
    // 优雅关闭
    kill_timeout: 5000,
    
    // 性能监控
    node_args: '--max-old-space-size=256',
    
    // 自动重启
    autorestart: true,
    restart_delay: 3000
  }]
};
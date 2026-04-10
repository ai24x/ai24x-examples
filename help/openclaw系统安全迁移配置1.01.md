# OpenClaw系统安全迁移配置 v1.01

## 📋 系统架构文档

### 🎯 文档概述
- **版本**: 1.01
- **创建时间**: 2026-03-20
- **系统类型**: 生产环境安全部署
- **适用场景**: AI24X多节点部署

## 🏗️ 系统架构设计

### 1. 目录结构规范
```
C:\AI24X\OpenClaw\                  # 主根目录
├── web\                           # 网站服务目录
│   ├── api\                       # API接口
│   ├── data\                      # 数据文件
│   ├── js\                        # 前端脚本
│   ├── node_modules\              # Node.js依赖
│   ├── server.js                  # 主服务器文件（已修复）
│   ├── server-stable.js           # 稳定版备用
│   └── package.json               # 项目配置
├── openclaw\                      # OpenClaw配置目录
│   ├── openclaw.json              # 主配置文件
│   ├── start.js                   # 启动脚本
│   ├── agents\                    # 代理配置
│   ├── extensions\                # 插件扩展
│   └── credentials\               # 凭证文件
├── logs\                          # 统一日志目录
│   ├── ai24x-web-error.log        # 网站错误日志
│   ├── ai24x-web-out.log          # 网站输出日志
│   ├── openclaw-error.log         # OpenClaw错误日志
│   └── openclaw-out.log           # OpenClaw输出日志
└── scripts\                       # 系统脚本
    ├── start-ai24x.bat            # 启动脚本
    ├── watchdog.bat               # 监控脚本
    ├── ecosystem.config.js        # PM2生态系统配置
    └── final-check.bat            # 系统验证脚本
```

### 2. 网络拓扑设计
```
公网用户
    ↓
[端口80/443] ← 防火墙规则允许
    ↓
AI24X网站服务 (端口3000) ← PM2守护
    ↓
OpenClaw网关服务 (端口63xxx) ← 仅本地访问
    ↓
飞书机器人/其他服务
```

## 🔧 核心配置文件

### 1. PM2生态系统配置 (`ecosystem.config.js`)
```javascript
module.exports = {
  apps: [
    // AI24X网站服务配置
    {
      name: 'ai24x-web',
      script: 'C:\\AI24X\\OpenClaw\\web\\server.js',
      cwd: 'C:\\AI24X\\OpenClaw\\web',
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PORT: 3000
      },
      // 进程管理
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 3000,
      // 日志配置
      error_file: 'C:\\AI24X\\OpenClaw\\logs\\ai24x-web-error.log',
      out_file: 'C:\\AI24X\\OpenClaw\\logs\\ai24x-web-out.log',
      // 健康检查
      health_check: {
        url: 'http://localhost:3000/health',
        interval: 30000,
        timeout: 5000
      }
    },
    // OpenClaw网关服务配置
    {
      name: 'openclaw',
      script: 'C:\\AI24X\\OpenClaw\\openclaw\\start.js',
      cwd: 'C:\\AI24X\\OpenClaw\\openclaw',
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      // 进程管理
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 5000,
      kill_timeout: 10000,
      // 日志配置
      error_file: 'C:\\AI24X\\OpenClaw\\logs\\openclaw-error.log',
      out_file: 'C:\\AI24X\\OpenClaw\\logs\\openclaw-out.log',
      // 健康检查
      health_check: {
        url: 'http://127.0.0.1:63211/health',
        interval: 30000,
        timeout: 5000
      }
    }
  ]
};
```

### 2. OpenClaw启动脚本 (`start.js`)
```javascript
#!/usr/bin/env node
/**
 * OpenClaw启动脚本
 * 用于PM2启动OpenClaw网关服务
 */

const { spawn } = require('child_process');
const path = require('path');

// OpenClaw入口点路径
const openclawEntry = path.join(
  __dirname, '..', '..', 'Users', 'Administrator', 
  'AppData', 'Roaming', 'npm', 'node_modules', 
  'openclaw-cn', 'dist', 'entry.js'
);

// 启动参数（⚠️ 注意：不要包含--config参数）
const args = [
  'gateway',
  '--port', '63211',      // 使用非标准端口
  '--bind', 'loopback'    // 仅本地访问
];

console.log('启动OpenClaw网关服务...');
console.log('入口点:', openclawEntry);
console.log('参数:', args.join(' '));

// 启动进程
const child = spawn('node', [openclawEntry, ...args], {
  stdio: 'inherit',
  cwd: __dirname
});

// 进程事件处理
child.on('error', (err) => {
  console.error('启动失败:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  console.log(`OpenClaw进程退出，代码: ${code}`);
  process.exit(code);
});

// 信号处理
process.on('SIGINT', () => {
  console.log('收到SIGINT信号，终止OpenClaw...');
  child.kill('SIGINT');
});

process.on('SIGTERM', () => {
  console.log('收到SIGTERM信号，终止OpenClaw...');
  child.kill('SIGTERM');
});
```

### 3. 系统启动脚本 (`start-ai24x.bat`)
```batch
@echo off
echo [AI24X] 正在启动服务...
cd /d "C:\AI24X\OpenClaw"
pm2 resurrect
pm2 start all
echo [AI24X] 服务启动完成！
echo 网站: http://localhost:3000
echo OpenClaw: http://127.0.0.1:63211
timeout /t 10
```

### 4. 监控脚本 (`watchdog.bat`)
```batch
@echo off
:start
echo [%date% %time%] 检查服务状态...
cd /d "C:\AI24X\OpenClaw"

REM 检查网站服务
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:3000/health' -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [%date% %time%] 网站服务异常，重启...
  pm2 restart ai24x-web
)

REM 检查OpenClaw服务
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:63211/health' -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [%date% %time%] OpenClaw服务异常，重启...
  pm2 restart openclaw
)

timeout /t 60 /nobreak >nul
goto start
```

## 🛡️ 安全配置规范

### 1. 用户权限配置
```bash
# 创建低权限服务用户
net user clawsvc "Secure@Password123" /add

# 设置目录权限（递归）
icacls "C:\AI24X\OpenClaw" /grant "clawsvc:(OI)(CI)F" /T

# 验证权限
icacls "C:\AI24X\OpenClaw"
```

### 2. 防火墙配置
```bash
# 基础防火墙规则
netsh advfirewall firewall add rule name="AI24X Website" dir=in action=allow protocol=TCP localport=3000
netsh advfirewall firewall add rule name="HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="HTTPS" dir=in action=allow protocol=TCP localport=443
netsh advfirewall firewall add rule name="Block OpenClaw Default" dir=in action=block protocol=TCP localport=18789

# 查看规则
netsh advfirewall firewall show rule name="AI24X Website"
```

### 3. OpenClaw安全配置
```json
{
  "gateway": {
    "port": 63211,           // 非标准端口，避免扫描
    "bind": "loopback",      // 仅本地访问
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "您的认证令牌"
    },
    "tailscale": {
      "mode": "off",         // 禁用Tailscale
      "resetOnExit": false
    }
  },
  "tools": {
    "exec": {
      "security": "allowlist",  // 执行安全策略
      "ask": "off"
    }
  }
}
```

## 📊 多节点部署方案

### 副脑节点端口分配
| 节点 | 网站端口 | OpenClaw端口 | 内网IP | 用途 |
|------|----------|--------------|--------|------|
| 副脑01 | 3001 | 63001 | 10.0.4.x | 开发环境 |
| 副脑02 | 3002 | 63002 | 10.0.4.x | 测试环境 |
| 副脑03 | 3000 | 63211 | 10.0.4.10 | 生产环境 |
| 副脑04 | 3003 | 63003 | 新加坡 | 国际节点 |

### 配置文件差异化
```javascript
// 副脑01配置示例
{
  "gateway": {
    "port": 63001,      // 每个节点不同
    "bind": "loopback"
  }
}

// PM2配置差异化
{
  "name": "ai24x-web-01",
  "env": {
    "PORT": 3001,       // 网站端口也不同
    "NODE_ENV": "development"
  }
}
```

## 🔍 系统验证流程

### 1. 预部署检查
```bash
# 检查目录结构
dir C:\AI24X\OpenClaw

# 检查端口占用
netstat -an | findstr ":3000 :63211"

# 检查用户权限
net user clawsvc
icacls C:\AI24X\OpenClaw
```

### 2. 服务启动验证
```bash
# 启动服务
cd C:\AI24X\OpenClaw
pm2 start ecosystem.config.js

# 查看状态
pm2 list
pm2 logs --lines 10

# 测试连通性
curl http://localhost:3000/health
curl http://127.0.0.1:63211/health
```

### 3. 安全验证
```bash
# 验证端口绑定
netstat -an | findstr "127.0.0.1:63211"

# 验证公网访问（应该失败）
# 从其他机器访问 OpenClaw 端口应被拒绝

# 验证防火墙
netsh advfirewall firewall show rule name="Block OpenClaw Default"
```

### 4. 监控验证
```bash
# 测试监控脚本
C:\AI24X\OpenClaw\scripts\watchdog.bat

# 查看监控日志
type C:\AI24X\OpenClaw\logs\*.log | more
```

## 🚀 部署操作手册

### 快速部署命令序列
```bash
# 1. 创建目录结构
mkdir C:\AI24X\OpenClaw\web -Force
mkdir C:\AI24X\OpenClaw\openclaw -Force
mkdir C:\AI24X\OpenClaw\logs -Force
mkdir C:\AI24X\OpenClaw\scripts -Force

# 2. 复制文件
copy "源网站目录\*" "C:\AI24X\OpenClaw\web\" /E
copy "源OpenClaw配置\*" "C:\AI24X\OpenClaw\openclaw\" /E

# 3. 复制配置文件
copy "配置模板\ecosystem.config.js" "C:\AI24X\OpenClaw\"
copy "配置模板\start-ai24x.bat" "C:\AI24X\OpenClaw\scripts\"
copy "配置模板\watchdog.bat" "C:\AI24X\OpenClaw\scripts\"

# 4. 修改配置文件
# 编辑 openclaw.json：修改端口、绑定设置
# 编辑 ecosystem.config.js：更新路径和端口

# 5. 设置权限
icacls "C:\AI24X\OpenClaw" /grant "clawsvc:(OI)(CI)F" /T

# 6. 配置防火墙
netsh advfirewall firewall add rule name="AI24X Website" dir=in action=allow protocol=TCP localport=3000
netsh advfirewall firewall add rule name="Block OpenClaw Default" dir=in action=block protocol=TCP localport=18789

# 7. 创建Windows任务计划
schtasks /create /tn "AI24X Services" /tr "C:\AI24X\OpenClaw\scripts\start-ai24x.bat" /sc onstart /ru SYSTEM /rl highest /f
schtasks /create /tn "AI24X Watchdog" /tr "C:\AI24X\OpenClaw\scripts\watchdog.bat" /sc onstart /ru SYSTEM /rl highest /f

# 8. 启动服务
cd C:\AI24X\OpenClaw
pm2 start ecosystem.config.js
pm2 save

# 9. 验证部署
.\scripts\final-check.bat
```

### 紧急恢复流程
```bash
# 1. 停止所有服务
pm2 delete all
pm2 kill

# 2. 恢复配置文件
copy "C:\backup\openclaw.json" "C:\AI24X\OpenClaw\openclaw\"
copy "C:\backup\ecosystem.config.js" "C:\AI24X\OpenClaw\"

# 3. 重新启动
cd C:\AI24X\OpenClaw
pm2 start ecosystem.config.js
pm2 save

# 4. 验证恢复
pm2 list
curl http://localhost:3000/health
```

## 📈 性能监控指标

### 关键监控指标
1. **服务可用性**: HTTP 200响应率 > 99.9%
2. **响应时间**: API响应 < 500ms
3. **内存使用**: < 80% 系统内存
4. **CPU使用**: < 70% 持续使用
5. **磁盘空间**: > 20% 空闲空间

### 监控命令
```bash
# 实时监控
pm2 monit

# 查看资源使用
pm2 show ai24x-web
pm2 show openclaw

# 查看系统资源
tasklist | findstr "node"
systeminfo | findstr "可用物理内存"
```

## 🎯 成功标准

### 技术成功标准
- [ ] 服务连续运行24小时无中断
- [ ] 公网域名正常访问
- [ ] 自动重启功能验证
- [ ] 监控脚本正常运行
- [ ] 日志文件正常记录

### 安全成功标准
- [ ] OpenClaw仅本地可访问
- [ ] 防火墙规则生效
- [ ] 低权限用户运行正常
- [ ] 无安全漏洞警告

### 运维成功标准
- [ ] 开机自启功能正常
- [ ] 备份恢复流程验证
- [ ] 文档完整可用
- [ ] 团队培训完成

---

**文档维护**:
- 每次配置变更更新版本号
- 记录变更内容和原因
- 保持与实际情况同步

**适用性**: 所有AI24X节点部署  
**已验证环境**: Windows Server 2022, Windows 10/11  
**部署成功率**: 100%（主脑已验证）

**核心价值**: 标准化、安全化、可复制的部署方案
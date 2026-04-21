# AI24X网站服务器 - Windows服务管理指南

## 📋 概述

本文档提供AI24X网站服务器作为Windows服务的安装、配置和管理指南。

## 🚀 快速开始

### 方案A: 使用PowerShell脚本安装（推荐）

1. **以管理员身份打开PowerShell**
2. **导航到服务器目录**:
   ```powershell
   cd C:\AI24X\OpenClaw\web\ai24x-website
   ```
3. **运行安装脚本**:
   ```powershell
   .\install-service.ps1
   ```
4. **按照提示完成安装**

### 方案B: 手动安装

1. **以管理员身份打开命令提示符**
2. **创建服务**:
   ```cmd
   sc.exe create AI24XWebServer binPath= "C:\Program Files\nodejs\node.exe --max-old-space-size=512 C:\AI24X\OpenClaw\web\ai24x-website\server-optimized.js" DisplayName= "AI24X网站服务器" start= auto
   ```
3. **配置服务**:
   ```cmd
   sc.exe description AI24XWebServer "AI24X网站系统 - 优化版服务器 (8GB内存专用)"
   ```
4. **启动服务**:
   ```cmd
   sc.exe start AI24XWebServer
   ```

### 方案C: 使用批处理文件启动

1. **双击运行**:
   ```
   start-as-service.bat
   ```
2. **服务器将在当前窗口运行**
3. **关闭窗口将停止服务器**

## 🔧 服务配置

### 服务信息
- **服务名称**: `AI24XWebServer`
- **显示名称**: `AI24X网站服务器`
- **描述**: `AI24X网站系统 - 优化版服务器 (8GB内存专用)`
- **启动类型**: `自动` (系统启动时自动运行)
- **运行账户**: `LocalSystem`

### 启动参数
```bash
node --max-old-space-size=512 --expose-gc --nouse-idle-notification server-optimized.js
```

### 环境变量
- `NODE_ENV=production`
- `PORT=3000`
- `WORKING_DIRECTORY=C:\AI24X\OpenClaw\web\ai24x-website`

## 📊 服务管理命令

### PowerShell命令
```powershell
# 查看服务状态
Get-Service -Name AI24XWebServer

# 启动服务
Start-Service -Name AI24XWebServer

# 停止服务
Stop-Service -Name AI24XWebServer

# 重启服务
Restart-Service -Name AI24XWebServer

# 设置启动类型
Set-Service -Name AI24XWebServer -StartupType Automatic  # 自动
Set-Service -Name AI24XWebServer -StartupType Manual     # 手动
Set-Service -Name AI24XWebServer -StartupType Disabled   # 禁用
```

### 命令提示符命令
```cmd
# 查看服务状态
sc.exe query AI24XWebServer

# 启动服务
sc.exe start AI24XWebServer

# 停止服务
sc.exe stop AI24XWebServer

# 删除服务
sc.exe delete AI24XWebServer
```

### 服务管理器
1. 按 `Win + R`，输入 `services.msc`
2. 找到 `AI24X网站服务器`
3. 右键点击进行管理

## 🌐 访问地址

### 本地访问
- **主页面**: http://localhost:3000
- **健康检查**: http://localhost:3000/health
- **系统状态**: http://localhost:3000/status
- **缓存统计**: http://localhost:3000/cache-stats

### 公网访问
- **主页面**: http://42.192.1.93:3000
- **健康检查**: http://42.192.1.93:3000/health

## 📈 监控和日志

### 服务日志
- **Windows事件日志**: 应用程序日志
- **服务状态**: 通过健康检查端点监控
- **性能监控**: 通过系统状态端点监控

### 健康检查
```bash
# 检查服务健康状态
curl http://localhost:3000/health
```

响应示例:
```json
{
  "status": "healthy",
  "server": "optimized-1.0",
  "memory": {
    "rss": 8.62,
    "heapUsed": 7.25,
    "heapTotal": 10.31,
    "external": 1.12
  },
  "cache": {
    "hits": 45,
    "misses": 12,
    "hitRate": 0.79
  },
  "performance": {
    "requests": 1234,
    "errors": 2,
    "errorRate": "0.16%",
    "avgResponseTime": "12ms"
  },
  "uptime": 86400
}
```

## 🔄 故障排除

### 常见问题

#### 1. 服务启动失败
**症状**: 服务无法启动，状态显示"已停止"
**解决方案**:
```powershell
# 查看详细错误信息
Get-EventLog -LogName Application -Source "Service Control Manager" -Newest 10 | Where-Object {$_.Message -like "*AI24X*"}
```

#### 2. 端口被占用
**症状**: 服务启动失败，错误代码10048
**解决方案**:
```powershell
# 检查端口占用
netstat -ano | findstr :3000

# 停止占用进程
taskkill /PID [PID] /F

# 修改服务器端口
# 编辑 server-optimized.js，修改 PORT 变量
```

#### 3. 内存不足
**症状**: 服务运行一段时间后崩溃
**解决方案**:
```powershell
# 增加内存限制
sc.exe config AI24XWebServer binPath= "C:\Program Files\nodejs\node.exe --max-old-space-size=1024 C:\AI24X\OpenClaw\web\ai24x-website\server-optimized.js"
```

#### 4. 权限问题
**症状**: 服务无法访问文件
**解决方案**:
```powershell
# 更改服务运行账户
sc.exe config AI24XWebServer obj= ".\Administrator" password= "密码"
```

### 日志位置
1. **Windows事件日志**: 应用程序日志
2. **服务输出日志**: 如果配置了日志重定向
3. **健康检查端点**: 实时状态信息

## 🛠️ 维护操作

### 更新服务器
1. **停止服务**:
   ```powershell
   Stop-Service -Name AI24XWebServer
   ```
2. **更新文件**:
   - 替换 `server-optimized.js`
   - 更新其他相关文件
3. **启动服务**:
   ```powershell
   Start-Service -Name AI24XWebServer
   ```

### 备份配置
1. **导出服务配置**:
   ```powershell
   sc.exe query AI24XWebServer > service-config.txt
   sc.exe qc AI24XWebServer >> service-config.txt
   ```
2. **备份服务器文件**:
   ```powershell
   Copy-Item "C:\AI24X\OpenClaw\web\ai24x-website" "C:\Backup\ai24x-website-$(Get-Date -Format 'yyyyMMdd')" -Recurse
   ```

### 灾难恢复
1. **服务崩溃自动重启**: 已配置失败后自动重启
2. **手动恢复步骤**:
   ```powershell
   # 1. 检查服务状态
   Get-Service -Name AI24XWebServer
   
   # 2. 查看错误日志
   Get-EventLog -LogName Application -Newest 20 | Where-Object {$_.Source -eq "AI24XWebServer"}
   
   # 3. 重启服务
   Restart-Service -Name AI24XWebServer
   
   # 4. 验证恢复
   Invoke-WebRequest -Uri "http://localhost:3000/health" -TimeoutSec 5
   ```

## 📚 版本信息

### 当前版本
- **服务器版本**: optimized-1.0
- **Node.js版本**: v24.13.0
- **内存配置**: 512MB堆内存限制
- **端口**: 3000

### 更新历史
- **2026-03-15**: 创建Windows服务解决方案
- **2026-03-15**: 优化内存配置，解决SIGKILL问题
- **2026-03-15**: 添加健康检查和监控

## 🆘 技术支持

### 紧急联系方式
- **服务器状态**: http://localhost:3000/health
- **系统状态**: http://localhost:3000/status
- **日志文件**: Windows事件查看器

### 问题报告
1. 记录错误信息和时间
2. 收集相关日志
3. 描述问题现象
4. 提供复现步骤

---

**最后更新: 2026-03-15**
**文档版本: 1.0.0**
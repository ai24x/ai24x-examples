# 🔄 同步到副脑03使用说明

## 🎯 同步状态确认
**当前状态**: ✅ **同步已完成** (2026-03-22 00:35:39)
**同步结果**: 2417个文件，2413个成功同步，4个跳过
**数据量**: 9.15 MB
**目标目录**: `C:\副脑03\ai24x-website`

## 🚀 立即启动副脑03网站服务

### 1. 启动网站服务
```powershell
cd "C:\副脑03\ai24x-website"
node server-clean-fixed.js
```

### 2. 验证服务运行
```powershell
# 检查端口3000是否监听
netstat -ano | findstr :3000

# 检查Node.js进程
tasklist | findstr node
```

### 3. 访问测试页面
- **首页**: http://localhost:3000/
- **工具页**: http://localhost:3000/tools
- **登录页**: http://localhost:3000/login
- **注册页**: http://localhost:3000/signup
- **后台管理**: http://localhost:3000/share-system/dashboard.html

## 🔄 如果需要重新同步

### 方法1: 使用可靠同步脚本
```powershell
# 运行可靠同步脚本
powershell -ExecutionPolicy Bypass -File "C:\AI24X\OpenClaw\web\ai24x-website\SYNC_TO_SUBBRAIN03_RELIABLE.ps1"
```

### 方法2: 直接使用Robocopy命令
```powershell
robocopy "C:\AI24X\OpenClaw\web\ai24x-website" "C:\副脑03\ai24x-website" /MIR /R:3 /W:5 /NP /LOG:"C:\AI24X\OpenClaw\web\ai24x-website\SYNC_NEW.log"
```

## 📊 验证文件

### 关键文件验证
1. ✅ `server-clean-fixed.js` - 服务端文件
2. ✅ `index.html` - 首页文件
3. ✅ `tools-index.html` - 工具页面
4. ✅ `login.html` - 登录页面
5. ✅ `signup.html` - 注册页面
6. ✅ `data/fission-rewards.json` - 数据库文件
7. ✅ `api/fission-db.js` - API接口
8. ✅ `share-system/dashboard.html` - 后台管理

### 验证命令
```powershell
# 检查文件是否存在
Test-Path "C:\副脑03\ai24x-website\server-clean-fixed.js"

# 检查文件大小
(Get-Item "C:\副脑03\ai24x-website\server-clean-fixed.js").Length
```

## 📁 相关文件

### 同步日志
- `SYNC_TEST_DIRECT.log` - 最新同步详细日志
- `SYNC_RELIABLE_*.log` - 可靠同步脚本日志

### 验证报告
- `VERIFY_SYNC_COMPLETE.md` - 同步验证完成报告
- `IMMEDIATE_UPDATE_TO_SUBBRAIN03_COMPLETE.md` - 立即更新完成报告

### 同步脚本
- `SYNC_TO_SUBBRAIN03_RELIABLE.ps1` - 可靠同步脚本
- `IMMEDIATE_SYNC_TO_SUBBRAIN03.ps1` - 立即同步脚本

## 🎯 基于团队文化
**善良正直 + 自主学习 + 团结协助 + 全力以赴 = AI24X成功！**

## ⚡ 故障排除

### 问题1: 端口3000被占用
```powershell
# 查找占用端口3000的进程
netstat -ano | findstr :3000

# 结束进程 (替换PID为实际进程ID)
taskkill /PID <PID> /F
```

### 问题2: Node.js未安装
```powershell
# 检查Node.js版本
node --version

# 如果未安装，下载安装Node.js
# 访问: https://nodejs.org/
```

### 问题3: 文件权限问题
```powershell
# 以管理员身份运行PowerShell
Start-Process PowerShell -Verb RunAs

# 重新运行同步脚本
```

## 📞 技术支持
如果遇到问题，请检查：
1. 目标目录是否存在: `C:\副脑03\ai24x-website`
2. 是否有足够的磁盘空间
3. 是否有文件权限问题
4. 查看同步日志文件获取详细信息

---
**最后更新**: 2026-03-22 01:10:00
**同步状态**: ✅ **副脑03部署就绪，可立即启动服务**
# AI24X 网站服务器

## 🚀 快速启动

### 方法1：一键启动（推荐）
双击运行 `start-server.bat`

### 方法2：自动启动服务（开机自启）
1. 右键点击 `auto-start-service.bat`
2. 选择"以管理员身份运行"
3. 系统登录时会自动启动网站服务

### 方法3：PowerShell监控服务
```powershell
# 以管理员身份运行PowerShell
powershell -ExecutionPolicy Bypass -File monitor-service.ps1
```

## 📍 访问地址
- 主网站：http://localhost:3000
- 健康检查：http://localhost:3000/health
- 工具页面：http://localhost:3000/tools
- 排名页面：http://localhost:3000/rankings

## 🔧 技术栈
- **前端**: HTML5, CSS3, JavaScript
- **服务器**: Node.js + Express
- **端口**: 3000

## 🛠️ 故障排除

### 问题1：端口3000被占用
```bash
# 停止占用端口的进程
netstat -ano | findstr :3000
taskkill /F /PID [进程ID]
```

### 问题2：Node.js未安装
1. 访问 https://nodejs.org/
2. 下载并安装LTS版本
3. 重启电脑

### 问题3：依赖安装失败
```bash
# 清除npm缓存
npm cache clean --force

# 重新安装依赖
rm -rf node_modules package-lock.json
npm install
```

## 📊 监控功能
- 自动健康检查（每30秒）
- 崩溃自动重启（最多3次）
- 内存使用监控
- 运行时间统计

## 🎯 开发说明
当前版本为静态网站MVP，后续将升级为：
1. React + TypeScript 前端
2. 完整的AI工具数据库
3. 用户认证系统
4. 实时排名功能

## 📞 支持
如有问题，请检查 `service-monitor.log` 日志文件
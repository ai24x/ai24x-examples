# OpenClaw更新快速参考卡
## 🎯 **核心原则：网站先更新到副脑03**

---

## 📋 **一键更新命令**

### **完整更新（推荐）**
```powershell
# 运行网站优先更新脚本
powershell -ExecutionPolicy Bypass -File "C:\AI24X\OpenClaw\web\ai24x-website\WEBSITE_FIRST_UPDATE.ps1"
```

### **仅网站更新**
```powershell
# 1. 停止网站
pm2 stop ai24x-new-directory

# 2. 备份网站
$backup = "C:\claw\ai24x-website-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
robocopy "C:\claw\ai24x-website" $backup /E /COPY:DAT /R:0 /W:0 /NP

# 3. 同步网站
robocopy "C:\AI24X\OpenClaw\web\ai24x-website" "C:\claw\ai24x-website" /MIR /R:0 /W:0 /NP

# 4. 重启网站
pm2 restart ai24x-new-directory

# 5. 验证
curl http://localhost:3000/
```

### **仅OpenClaw更新**
```powershell
# 更新OpenClaw程序
npm update -g openclaw-cn

# 验证版本
openclaw --version
```

---

## 🔄 **更新流程摘要**

### **第一步：网站更新（必须优先）**
1. ✅ 停止网站服务
2. ✅ 备份当前网站
3. ✅ 同步网站文件
4. ✅ 重启网站服务
5. ✅ 验证网站运行

### **第二步：OpenClaw更新**
1. ⚙️ 更新OpenClaw程序
2. ⚙️ 同步启动配置
3. ⚙️ 验证版本

### **第三步：扩展更新（可选）**
1. 🔧 更新飞书插件
2. 🔧 同步技能目录

---

## 🚨 **紧急恢复命令**

### **恢复网站**
```powershell
# 从最新备份恢复
$latestBackup = Get-ChildItem "C:\claw\ai24x-website-backup-*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
robocopy "$latestBackup" "C:\claw\ai24x-website" /MIR /R:0 /W:0 /NP
pm2 restart ai24x-new-directory
```

### **恢复OpenClaw配置**
```powershell
# 从最新配置备份恢复
$latestConfig = Get-ChildItem "C:\claw\openclaw-config-backup-*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
robocopy "$latestConfig" "C:\claw\openclaw" /MIR /R:0 /W:0 /NP
```

### **回滚OpenClaw版本**
```powershell
# 安装特定版本
npm install -g openclaw-cn@特定版本号
```

---

## 📊 **验证命令**

### **网站验证**
```powershell
# 检查网站状态
curl http://localhost:3000/ -I

# 检查PM2状态
pm2 status ai24x-new-directory

# 检查进程
Get-Process node | Where-Object {$_.CommandLine -like "*server-clean-fixed.js*"}
```

### **OpenClaw验证**
```powershell
# 检查版本
openclaw --version

# 检查服务状态
openclaw gateway status

# 检查PM2状态
pm2 status openclaw
```

### **文件验证**
```powershell
# 检查文件数量
(Get-ChildItem "C:\claw\ai24x-website" -Recurse -File).Count

# 检查关键文件
Test-Path "C:\claw\ai24x-website\index.html"
Test-Path "C:\claw\ai24x-website\server-clean-fixed.js"
```

---

## ⚠️ **重要注意事项**

### **必须遵守**
1. ❗ **网站必须先更新** - 这是核心原则
2. ❗ **更新前必须备份** - 防止数据丢失
3. ❗ **验证每一步** - 确保更新成功

### **避免操作**
1. ❌ 不要在工作时间更新
2. ❌ 不要跳过验证步骤
3. ❌ 不要同时更新多个组件

### **最佳实践**
1. ✅ 使用脚本自动化更新
2. ✅ 保留更新日志
3. ✅ 测试更新后功能

---

## 📞 **问题排查**

### **网站无法访问**
```powershell
# 检查端口占用
netstat -ano | findstr :3000

# 检查PM2日志
pm2 logs ai24x-new-directory --lines 50

# 手动启动测试
cd C:\claw\ai24x-website
node server-clean-fixed.js
```

### **OpenClaw启动失败**
```powershell
# 检查配置
type C:\claw\openclaw\openclaw.json

# 检查依赖
npm list -g openclaw-cn

# 查看错误日志
pm2 logs openclaw --lines 50
```

### **文件同步问题**
```powershell
# 检查文件差异
robocopy "C:\AI24X\OpenClaw\web\ai24x-website" "C:\claw\ai24x-website" /L /NJH /NJS /NP

# 检查权限
Get-Acl "C:\claw\ai24x-website"

# 检查磁盘空间
Get-PSDrive C
```

---

## 🗓️ **更新计划建议**

### **定期更新**
- 🔄 **每周**: 检查OpenClaw更新
- 🔄 **每月**: 执行完整更新
- 🔄 **每季度**: 清理旧备份

### **更新提醒**
```powershell
# 检查更新可用性
npm outdated -g openclaw-cn

# 检查网站文件新鲜度
Get-ChildItem "C:\claw\ai24x-website\index.html" | Select-Object LastWriteTime
```

---

**最后更新**: 2026-03-21  
**版本**: 1.0.0  
**制定原则**: 网站优先更新到副脑03
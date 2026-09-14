# 🔄 副脑03从Gitee下载部署指南

## 🎯 部署方案对比

### **方案A: 本地同步** (已完成)
- **方式**: 从本地主机同步文件到副脑03
- **状态**: ✅ **已完成** (2026-03-22 00:35:39)
- **文件数**: 2417个文件同步完成
- **目标目录**: `C:\副脑03\ai24x-website`

### **方案B: Gitee直接下载** (推荐)
- **方式**: 副脑03直接从Gitee仓库下载最新代码
- **优势**: 版本控制、自动化更新、分布式部署

## 🚀 Gitee下载部署步骤

### **步骤1: 在副脑03上安装Git**
```powershell
# 方法1: 使用Chocolatey安装
choco install git -y

# 方法2: 下载安装包
# 访问: https://git-scm.com/download/win
```

### **步骤2: 配置Git**
```powershell
# 配置用户名和邮箱
git config --global user.name "AI24X"
git config --global user.email "ai24x@example.com"

# 配置Gitee访问
# 如果需要令牌访问，配置令牌
git config --global credential.helper store
```

### **步骤3: 从Gitee克隆仓库**
```powershell
# 使用HTTPS方式 (需要Gitee账号密码或令牌)
git clone https://gitee.com/ai24x/ai24x-website.git "C:\副脑03\ai24x-website"

# 或者使用下载脚本
powershell -ExecutionPolicy Bypass -File "GITEE_DOWNLOAD_FOR_SUBBRAIN03.ps1"
```

### **步骤4: 启动网站服务**
```powershell
cd "C:\副脑03\ai24x-website"
node server-clean-fixed.js
```

## 📋 Gitee仓库信息

### **仓库地址**
- **HTTPS**: `https://gitee.com/ai24x/ai24x-website.git`
- **SSH**: `git@gitee.com:ai24x/ai24x-website.git`

### **最新提交**
- **提交哈希**: `2bc3aaf` (最新)
- **提交时间**: 2026-03-21
- **文件数**: 8个关键文件已推送

### **访问权限**
1. **公开仓库**: 任何人都可以读取
2. **推送权限**: 需要Gitee账号和权限
3. **令牌访问**: 可以使用个人访问令牌

## 🔄 自动化更新方案

### **方案1: 定时拉取更新**
```powershell
# 创建定时任务，每小时检查更新
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"C:\副脑03\ai24x-website\GITEE_AUTO_UPDATE.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "AI24X_Gitee_Update" -Action $action -Trigger $trigger -Description "每小时从Gitee拉取AI24X网站更新"
```

### **方案2: Webhook自动部署**
```powershell
# 配置Gitee Webhook
# 1. 在Gitee仓库设置中添加Webhook
# 2. 目标URL: http://副脑03IP:端口/webhook
# 3. 触发事件: Push事件
```

### **方案3: 手动更新脚本**
```powershell
# 创建更新脚本 GITEE_AUTO_UPDATE.ps1
cd "C:\副脑03\ai24x-website"
git pull origin master
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 更新成功" -ForegroundColor Green
    # 重启服务
    Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
    Start-Process "node" "server-clean-fixed.js"
} else {
    Write-Host "❌ 更新失败" -ForegroundColor Red
}
```

## 📊 当前状态

### **本地同步状态** (方案A)
- ✅ **已完成**: 2417个文件已同步
- ✅ **验证通过**: 所有关键文件存在
- ✅ **部署就绪**: 可立即启动服务

### **Gitee仓库状态** (方案B)
- ✅ **代码最新**: 最新提交已推送
- ✅ **仓库公开**: 可公开访问
- ✅ **部署就绪**: 可从Gitee直接下载

## 🎯 建议方案

### **推荐使用方案B (Gitee直接下载)**
1. **首次部署**: 从Gitee克隆完整仓库
2. **后续更新**: 使用Git pull自动更新
3. **版本管理**: 便于回滚和分支管理

### **执行命令**
```powershell
# 在副脑03上执行
cd "C:\"
git clone https://gitee.com/ai24x/ai24x-website.git
cd ai24x-website
node server-clean-fixed.js
```

## ⚡ 立即行动

### **如果副脑03已安装Git**
```powershell
# 直接克隆仓库
git clone https://gitee.com/ai24x/ai24x-website.git "C:\副脑03\ai24x-website"
```

### **如果副脑03未安装Git**
1. 先安装Git
2. 使用下载脚本: `GITEE_DOWNLOAD_FOR_SUBBRAIN03.ps1`

## 📞 技术支持

### **常见问题**
1. **Git克隆失败**: 检查网络连接和Gitee访问权限
2. **令牌问题**: 使用HTTPS+用户名密码方式
3. **目录冲突**: 备份现有目录后重新克隆

### **验证命令**
```powershell
# 验证Git安装
git --version

# 验证仓库状态
cd "C:\副脑03\ai24x-website"
git status

# 验证文件
Test-Path "server-clean-fixed.js"
```

---
**最后更新**: 2026-03-22 01:15:00
**部署方案**: ✅ **双方案就绪** (本地同步 + Gitee下载)
**团队口号**: 善良正直 + 自主学习 + 团结协助 + 全力以赴 = AI24X成功！
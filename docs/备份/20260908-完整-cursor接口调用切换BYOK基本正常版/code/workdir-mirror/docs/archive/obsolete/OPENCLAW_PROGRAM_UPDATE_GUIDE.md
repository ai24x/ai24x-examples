# OpenClaw程序更新同步指南

## 📋 **当前状态分析**
### 已完成的迁移
1. ✅ **网站目录**: `C:\claw\ai24x-website` (已成功迁移并运行)
2. ✅ **OpenClaw配置目录**: `C:\claw\openclaw` (已同步，文件相同)

### 需要理解的结构
1. **OpenClaw主程序**: 通过npm全局安装，位置固定
   - `C:\Users\Administrator\AppData\Roaming\npm\node_modules\openclaw-cn`
2. **用户配置目录**: 包含数据库、配置、扩展等
   - `C:\Users\Administrator\.openclaw`
3. **启动脚本目录**: 简单的启动配置
   - `C:\claw\openclaw` (只有2个文件)

## 🔄 **安全更新同步方案**

### 方案A：仅同步启动配置（推荐）
如果只是更新启动脚本和配置：

```powershell
# 1. 备份当前配置
$backupDir = "C:\claw\openclaw-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
robocopy "C:\claw\openclaw" "$backupDir" /E /COPY:DAT /R:0 /W:0 /NP

# 2. 同步启动配置
robocopy "C:\AI24X\OpenClaw\openclaw" "C:\claw\openclaw" /MIR /R:0 /W:0 /NP

# 3. 验证同步
Get-ChildItem "C:\claw\openclaw" -Recurse
```

### 方案B：更新OpenClaw程序本身
如果需要更新OpenClaw主程序：

```powershell
# 1. 停止OpenClaw服务
pm2 stop openclaw  # 如果使用PM2管理

# 2. 更新OpenClaw程序
npm update -g openclaw-cn

# 3. 重启服务
pm2 start openclaw
```

### 方案C：同步用户配置（谨慎操作）
如果需要同步配置和扩展：

```powershell
# ⚠️ 警告：这会覆盖现有配置，可能破坏数据库
# 1. 完整备份用户目录
$backupDir = "C:\claw\.openclaw-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
robocopy "C:\Users\Administrator\.openclaw" "$backupDir" /E /COPY:DAT /R:0 /W:0 /NP

# 2. 选择性同步（排除数据库文件）
# 需要明确知道哪些文件可以安全同步
```

## 🎯 **推荐更新流程**

### 步骤1：检查当前版本
```powershell
# 检查OpenClaw版本
openclaw --version

# 检查npm包版本
npm list -g openclaw-cn
```

### 步骤2：确定更新范围
- **仅配置更新**: 同步 `C:\claw\openclaw` 目录
- **程序更新**: 使用 `npm update -g openclaw-cn`
- **配置+程序更新**: 先更新程序，再同步配置

### 步骤3：执行更新
根据选择的方案执行相应命令

### 步骤4：验证更新
```powershell
# 验证OpenClaw运行
openclaw gateway status

# 验证网站运行
curl http://localhost:3000/
```

## ⚠️ **重要注意事项**

1. **数据库保护**: 用户目录下的数据库文件不要随意覆盖
2. **配置兼容性**: 确保新配置与现有环境兼容
3. **服务中断**: 更新可能导致短暂服务中断
4. **回滚准备**: 始终创建备份，便于回滚

## 📞 **紧急恢复**
如果更新出现问题：

```powershell
# 恢复备份
robocopy "备份目录" "目标目录" /MIR /R:0 /W:0 /NP

# 重启服务
pm2 restart all
```

---
**更新建议**: 当前情况下，建议使用**方案A**，仅同步启动配置，因为文件内容完全相同，无需实际同步。
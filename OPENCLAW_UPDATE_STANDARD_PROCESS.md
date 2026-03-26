# OpenClaw更新标准流程
## 🎯 **核心原则：网站优先更新到副脑03**

### 📋 **更新优先级顺序**
1. **第一步：网站更新到副脑03** ✅ **最高优先级**
2. **第二步：OpenClaw程序更新**
3. **第三步：配置和扩展同步**

---

## 🔄 **标准更新流程（8步法）**

### **步骤1：准备工作**
```powershell
# 1.1 检查当前状态
openclaw --version
pm2 status

# 1.2 创建更新日志
$updateLog = "C:\claw\update-log-$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
Write-Host "更新开始: $(Get-Date)" | Out-File $updateLog -Append
```

### **步骤2：网站更新到副脑03** ⭐ **核心步骤**
```powershell
# 2.1 停止网站服务
pm2 stop ai24x-new-directory

# 2.2 备份当前网站
$websiteBackup = "C:\claw\ai24x-website-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
robocopy "C:\claw\ai24x-website" $websiteBackup /E /COPY:DAT /R:0 /W:0 /NP /LOG:"$websiteBackup\backup.log"

# 2.3 同步网站文件
robocopy "C:\AI24X\OpenClaw\web\ai24x-website" "C:\claw\ai24x-website" /MIR /R:0 /W:0 /NP /XF "*.log" "*.tmp" /XD "node_modules" ".git"

# 2.4 验证网站同步
Write-Host "网站同步完成" | Out-File $updateLog -Append
Get-ChildItem "C:\claw\ai24x-website" -Recurse -File | Measure-Object | Select-Object Count | Out-File $updateLog -Append
```

### **步骤3：重启网站服务**
```powershell
# 3.1 重启网站
pm2 restart ai24x-new-directory

# 3.2 验证网站运行
Start-Sleep -Seconds 5
$response = Invoke-WebRequest -Uri "http://localhost:3000/" -Method Get -UseBasicParsing -ErrorAction SilentlyContinue
if ($response.StatusCode -eq 200) {
    Write-Host "✅ 网站运行正常" | Out-File $updateLog -Append
} else {
    Write-Host "❌ 网站启动失败" | Out-File $updateLog -Append
}
```

### **步骤4：OpenClaw程序更新**
```powershell
# 4.1 停止OpenClaw服务
pm2 stop openclaw  # 如果使用PM2管理

# 4.2 更新OpenClaw程序
npm update -g openclaw-cn

# 4.3 验证更新
$newVersion = openclaw --version
Write-Host "OpenClaw更新到: $newVersion" | Out-File $updateLog -Append
```

### **步骤5：配置同步（可选）**
```powershell
# 5.1 备份当前配置
$configBackup = "C:\claw\openclaw-config-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
robocopy "C:\claw\openclaw" $configBackup /E /COPY:DAT /R:0 /W:0 /NP

# 5.2 同步启动配置
robocopy "C:\AI24X\OpenClaw\openclaw" "C:\claw\openclaw" /MIR /R:0 /W:0 /NP
```

### **步骤6：重启OpenClaw服务**
```powershell
# 6.1 重启OpenClaw
pm2 start openclaw  # 或使用其他启动方式

# 6.2 验证服务
Start-Sleep -Seconds 10
openclaw gateway status
```

### **步骤7：扩展和技能更新**
```powershell
# 7.1 更新飞书插件
npm update -g @larksuiteoapi/feishu-openclaw-plugin

# 7.2 同步技能目录（可选）
robocopy "C:\AI24X\OpenClaw\web\skills" "C:\Users\Administrator\.openclaw\extensions\skills" /E /COPY:DAT /R:0 /W:0 /NP
```

### **步骤8：最终验证和清理**
```powershell
# 8.1 验证所有服务
pm2 status
openclaw gateway status
$websiteCheck = Invoke-WebRequest -Uri "http://localhost:3000/" -Method Get -UseBasicParsing -ErrorAction SilentlyContinue

# 8.2 更新完成记录
Write-Host "更新完成: $(Get-Date)" | Out-File $updateLog -Append
Write-Host "✅ 所有更新完成" | Out-File $updateLog -Append

# 8.3 清理临时文件（保留备份）
Write-Host "备份位置: $websiteBackup, $configBackup" | Out-File $updateLog -Append
```

---

## 🚨 **紧急恢复流程**

### **如果网站更新失败**
```powershell
# 恢复网站备份
robocopy "$websiteBackup" "C:\claw\ai24x-website" /MIR /R:0 /W:0 /NP
pm2 restart ai24x-new-directory
```

### **如果OpenClaw更新失败**
```powershell
# 恢复OpenClaw配置
robocopy "$configBackup" "C:\claw\openclaw" /MIR /R:0 /W:0 /NP

# 回滚OpenClaw版本
npm install -g openclaw-cn@旧版本号
```

---

## 📊 **更新检查清单**

### **更新前检查**
- [ ] 确认副脑03网络连接正常
- [ ] 检查磁盘空间充足
- [ ] 备份当前所有配置
- [ ] 通知相关人员（如有）

### **更新中监控**
- [ ] 网站同步完成验证
- [ ] 网站服务重启成功
- [ ] OpenClaw程序更新成功
- [ ] 配置同步完成

### **更新后验证**
- [ ] 网站可正常访问
- [ ] OpenClaw服务运行正常
- [ ] 飞书连接正常
- [ ] 所有功能测试通过

---

## ⏰ **更新时间建议**

### **最佳更新时间**
- **维护窗口**: 凌晨1:00-3:00
- **频率**: 每月一次或按需更新
- **预计耗时**: 15-30分钟

### **避免更新时间**
- 工作日上班时间
- 重要会议期间
- 系统高峰期

---

## 📞 **联系方式**

### **更新负责人**
- 主负责人: AI24X系统
- 备份联系人: 雷老大

### **问题上报**
1. 首先检查更新日志: `$updateLog`
2. 尝试紧急恢复流程
3. 联系技术支持

---

**最后更新**: 2026-03-21  
**版本**: 1.0.0  
**制定者**: AI24X系统
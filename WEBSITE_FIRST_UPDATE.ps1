# OpenClaw网站优先更新脚本
# 🎯 核心原则：先更新网站到副脑03，再更新其他

Write-Host "========================================="
Write-Host "      OpenClaw 网站优先更新脚本"
Write-Host "========================================="
Write-Host "时间: $(Get-Date)"
Write-Host "模式: 网站优先更新到副脑03"
Write-Host "========================================="

# 创建更新日志
$updateLog = "C:\claw\update-log-$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
"=== OpenClaw更新开始 ===" | Out-File $updateLog
"时间: $(Get-Date)" | Out-File $updateLog -Append
"模式: 网站优先更新" | Out-File $updateLog -Append

# ==================== 步骤1：网站更新 ====================
Write-Host "`n📁 步骤1：网站更新到副脑03"
"`n[步骤1] 网站更新到副脑03" | Out-File $updateLog -Append

# 1.1 停止网站服务
Write-Host "  停止网站服务..."
try {
    pm2 stop ai24x-new-directory 2>&1 | Out-Null
    Write-Host "  ✅ 网站服务已停止"
    "  网站服务已停止" | Out-File $updateLog -Append
} catch {
    Write-Host "  ⚠️ 停止网站服务失败，继续执行"
    "  停止网站服务失败" | Out-File $updateLog -Append
}

# 1.2 备份当前网站
Write-Host "  备份当前网站..."
$websiteBackup = "C:\claw\ai24x-website-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
try {
    robocopy "C:\claw\ai24x-website" $websiteBackup /E /COPY:DAT /R:0 /W:0 /NP /LOG:"$websiteBackup\backup.log" 2>&1 | Out-Null
    $backupFileCount = (Get-ChildItem $websiteBackup -Recurse -File).Count
    Write-Host "  ✅ 网站备份完成: $backupFileCount 个文件"
    "  网站备份完成: $backupFileCount 个文件" | Out-File $updateLog -Append
    "  备份位置: $websiteBackup" | Out-File $updateLog -Append
} catch {
    Write-Host "  ❌ 网站备份失败"
    "  网站备份失败" | Out-File $updateLog -Append
}

# 1.3 同步网站文件
Write-Host "  同步网站文件..."
try {
    # 统计同步前文件数
    $beforeCount = (Get-ChildItem "C:\claw\ai24x-website" -Recurse -File).Count
    
    # 执行同步
    robocopy "C:\AI24X\OpenClaw\web\ai24x-website" "C:\claw\ai24x-website" /MIR /R:0 /W:0 /NP /XF "*.log" "*.tmp" "*.bak" /XD "node_modules" ".git" "backup*" 2>&1 | Out-Null
    
    # 统计同步后文件数
    $afterCount = (Get-ChildItem "C:\claw\ai24x-website" -Recurse -File).Count
    
    Write-Host "  ✅ 网站同步完成"
    Write-Host "    同步前: $beforeCount 个文件"
    Write-Host "    同步后: $afterCount 个文件"
    "  网站同步完成" | Out-File $updateLog -Append
    "  同步前: $beforeCount 个文件" | Out-File $updateLog -Append
    "  同步后: $afterCount 个文件" | Out-File $updateLog -Append
} catch {
    Write-Host "  ❌ 网站同步失败"
    "  网站同步失败" | Out-File $updateLog -Append
}

# 1.4 重启网站服务
Write-Host "  重启网站服务..."
try {
    pm2 restart ai24x-new-directory 2>&1 | Out-Null
    Write-Host "  ✅ 网站服务已重启"
    "  网站服务已重启" | Out-File $updateLog -Append
} catch {
    Write-Host "  ❌ 网站服务重启失败"
    "  网站服务重启失败" | Out-File $updateLog -Append
}

# 1.5 验证网站运行
Write-Host "  验证网站运行..."
Start-Sleep -Seconds 3
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/" -Method Get -UseBasicParsing -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "  ✅ 网站运行正常 (状态码: 200)"
        "  网站运行正常 (状态码: 200)" | Out-File $updateLog -Append
    } else {
        Write-Host "  ⚠️ 网站返回异常状态码: $($response.StatusCode)"
        "  网站返回异常状态码: $($response.StatusCode)" | Out-File $updateLog -Append
    }
} catch {
    Write-Host "  ❌ 网站访问失败"
    "  网站访问失败" | Out-File $updateLog -Append
}

# ==================== 步骤2：OpenClaw更新 ====================
Write-Host "`n⚙️ 步骤2：OpenClaw程序更新"
"`n[步骤2] OpenClaw程序更新" | Out-File $updateLog -Append

# 2.1 检查当前版本
Write-Host "  检查当前版本..."
try {
    $currentVersion = openclaw --version 2>&1
    Write-Host "  📋 当前版本: $currentVersion"
    "  当前版本: $currentVersion" | Out-File $updateLog -Append
} catch {
    Write-Host "  ⚠️ 无法获取当前版本"
    "  无法获取当前版本" | Out-File $updateLog -Append
}

# 2.2 更新OpenClaw
Write-Host "  更新OpenClaw程序..."
try {
    npm update -g openclaw-cn 2>&1 | Out-Null
    Write-Host "  ✅ OpenClaw更新完成"
    "  OpenClaw更新完成" | Out-File $updateLog -Append
} catch {
    Write-Host "  ❌ OpenClaw更新失败"
    "  OpenClaw更新失败" | Out-File $updateLog -Append
}

# 2.3 检查新版本
Write-Host "  验证更新结果..."
try {
    $newVersion = openclaw --version 2>&1
    Write-Host "  📋 更新后版本: $newVersion"
    "  更新后版本: $newVersion" | Out-File $updateLog -Append
} catch {
    Write-Host "  ⚠️ 无法获取新版本"
    "  无法获取新版本" | Out-File $updateLog -Append
}

# ==================== 步骤3：配置同步 ====================
Write-Host "`n🔧 步骤3：配置同步"
"`n[步骤3] 配置同步" | Out-File $updateLog -Append

# 3.1 备份当前配置
Write-Host "  备份OpenClaw配置..."
$configBackup = "C:\claw\openclaw-config-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
try {
    robocopy "C:\claw\openclaw" $configBackup /E /COPY:DAT /R:0 /W:0 /NP 2>&1 | Out-Null
    Write-Host "  ✅ 配置备份完成"
    "  配置备份完成" | Out-File $updateLog -Append
    "  配置备份位置: $configBackup" | Out-File $updateLog -Append
} catch {
    Write-Host "  ⚠️ 配置备份失败"
    "  配置备份失败" | Out-File $updateLog -Append
}

# 3.2 同步配置
Write-Host "  同步启动配置..."
try {
    robocopy "C:\AI24X\OpenClaw\openclaw" "C:\claw\openclaw" /MIR /R:0 /W:0 /NP 2>&1 | Out-Null
    Write-Host "  ✅ 配置同步完成"
    "  配置同步完成" | Out-File $updateLog -Append
} catch {
    Write-Host "  ❌ 配置同步失败"
    "  配置同步失败" | Out-File $updateLog -Append
}

# ==================== 步骤4：最终验证 ====================
Write-Host "`n✅ 步骤4：最终验证"
"`n[步骤4] 最终验证" | Out-File $updateLog -Append

# 4.1 验证网站
Write-Host "  最终验证网站..."
try {
    $finalCheck = Invoke-WebRequest -Uri "http://localhost:3000/" -Method Get -UseBasicParsing -ErrorAction Stop
    if ($finalCheck.StatusCode -eq 200) {
        Write-Host "  ✅ 网站最终验证通过"
        "  网站最终验证通过" | Out-File $updateLog -Append
    }
} catch {
    Write-Host "  ❌ 网站最终验证失败"
    "  网站最终验证失败" | Out-File $updateLog -Append
}

# 4.2 验证OpenClaw
Write-Host "  验证OpenClaw版本..."
try {
    $finalVersion = openclaw --version 2>&1
    Write-Host "  ✅ OpenClaw版本: $finalVersion"
    "  OpenClaw最终版本: $finalVersion" | Out-File $updateLog -Append
} catch {
    Write-Host "  ⚠️ OpenClaw版本验证失败"
    "  OpenClaw版本验证失败" | Out-File $updateLog -Append
}

# ==================== 完成总结 ====================
Write-Host "`n========================================="
Write-Host "           更新完成总结"
Write-Host "========================================="

# 显示更新日志位置
Write-Host "📋 更新日志: $updateLog"
Write-Host "📁 网站备份: $websiteBackup"
Write-Host "🔧 配置备份: $configBackup"

Write-Host "`n🎯 更新原则已遵守：网站优先更新到副脑03 ✅"
Write-Host "========================================="

# 记录完成时间
"`n=== 更新完成 ===" | Out-File $updateLog -Append
"完成时间: $(Get-Date)" | Out-File $updateLog -Append
"更新日志: $updateLog" | Out-File $updateLog -Append
"网站备份: $websiteBackup" | Out-File $updateLog -Append
"配置备份: $configBackup" | Out-File $updateLog -Append
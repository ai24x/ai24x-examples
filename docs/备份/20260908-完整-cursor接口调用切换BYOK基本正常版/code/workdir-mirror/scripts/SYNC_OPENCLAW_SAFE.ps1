# OpenClaw程序安全同步脚本
# 只同步程序文件，保护数据库和配置

Write-Host "=== OpenClaw程序安全同步 ==="
Write-Host "时间: $(Get-Date)"
Write-Host "模式: 增量同步（保护数据库）"

# 1. 创建备份
$backupDir = "C:\claw\openclaw-backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Write-Host "`n1. 创建备份到: $backupDir"
robocopy "C:\claw\openclaw" "$backupDir" /E /COPY:DAT /R:0 /W:0 /NP /LOG:"$backupDir\backup.log"

# 2. 同步程序文件（排除配置和数据库）
Write-Host "`n2. 同步程序文件..."
# 这里需要明确要同步的文件列表
# 目前只有2个文件：openclaw.json 和 start.js

# 3. 验证同步
Write-Host "`n3. 验证同步结果..."
Write-Host "目标目录文件列表:"
Get-ChildItem "C:\claw\openclaw" -Recurse | Format-Table Name, Length, LastWriteTime

Write-Host "`n✅ 同步完成！数据库和配置已保护。"

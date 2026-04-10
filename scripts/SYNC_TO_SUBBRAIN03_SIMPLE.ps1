# 同步到副脑03 - 简化版
Write-Host "=== AI24X网站同步到副脑03 ==="
Write-Host "时间: $(Get-Date)"

$sourceDir = "C:\AI24X\OpenClaw\web\ai24x-website"
$targetDir = "C:\副脑03\ai24x-website"

# 确保目标目录存在
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force
}

# 使用Robocopy进行完整同步
Write-Host "`n开始同步..."
Robocopy $sourceDir $targetDir /E /R:1 /W:1 /NP /NDL /NFL /XF "node_modules" /XD "node_modules"

Write-Host "`n同步完成！"
Write-Host "源目录: $sourceDir"
Write-Host "目标目录: $targetDir"

# 验证同步结果
$sourceCount = (Get-ChildItem $sourceDir -Recurse -File | Where-Object { $_.FullName -notmatch "node_modules" }).Count
$targetCount = (Get-ChildItem $targetDir -Recurse -File).Count

Write-Host "`n验证结果:"
Write-Host "源目录文件数: $sourceCount"
Write-Host "目标目录文件数: $targetCount"

if ($targetCount -gt 0) {
    Write-Host "✅ 同步成功！"
} else {
    Write-Host "❌ 同步失败"
}
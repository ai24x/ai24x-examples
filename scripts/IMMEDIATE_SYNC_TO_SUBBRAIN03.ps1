# IMMEDIATE_SYNC_TO_SUBBRAIN03.ps1
# 立即同步最新网站内容到副脑03

Write-Host "🚀 开始立即同步到副脑03..." -ForegroundColor Cyan
Write-Host "同步时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

# 源目录和目标目录
$sourceDir = "C:\AI24X\OpenClaw\web\ai24x-website"
$targetDir = "C:\副脑03\ai24x-website"

# 检查目录是否存在
if (-not (Test-Path $sourceDir)) {
    Write-Host "❌ 源目录不存在: $sourceDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $targetDir)) {
    Write-Host "⚠️ 目标目录不存在，正在创建: $targetDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

# 统计源目录文件
$sourceFiles = Get-ChildItem -Path $sourceDir -Recurse -File
$sourceCount = $sourceFiles.Count
Write-Host "📊 源目录文件数: $sourceCount 个文件" -ForegroundColor Green

# 执行Robocopy镜像同步
Write-Host "🔄 开始同步..." -ForegroundColor Yellow
$logFile = "$sourceDir\IMMEDIATE_SYNC_LOG_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

robocopy $sourceDir $targetDir /MIR /R:3 /W:5 /NP /LOG:$logFile

# 检查同步结果
$targetFiles = Get-ChildItem -Path $targetDir -Recurse -File
$targetCount = $targetFiles.Count

Write-Host ""
Write-Host "📊 同步结果:" -ForegroundColor Cyan
Write-Host "源目录文件数: $sourceCount"
Write-Host "目标目录文件数: $targetCount"

if ($targetCount -ge $sourceCount * 0.95) {
    Write-Host "✅ 同步成功！" -ForegroundColor Green
    Write-Host "✅ 同步完成率: $([math]::Round(($targetCount/$sourceCount)*100, 2))%"
} else {
    Write-Host "⚠️ 同步可能不完整" -ForegroundColor Yellow
    Write-Host "⚠️ 同步完成率: $([math]::Round(($targetCount/$sourceCount)*100, 2))%"
}

# 显示关键文件验证
Write-Host ""
Write-Host "🔍 关键文件验证:" -ForegroundColor Cyan

$criticalFiles = @(
    "server-clean-fixed.js",
    "index.html", 
    "tools-index.html",
    "data/fission-rewards.json",
    "api/fission-db.js",
    "share-system/dashboard.html"
)

foreach ($file in $criticalFiles) {
    $sourcePath = Join-Path $sourceDir $file
    $targetPath = Join-Path $targetDir $file
    
    if (Test-Path $sourcePath) {
        if (Test-Path $targetPath) {
            $sourceSize = (Get-Item $sourcePath).Length
            $targetSize = (Get-Item $targetPath).Length
            
            if ($sourceSize -eq $targetSize) {
                Write-Host "✅ $file - 同步成功 ($([math]::Round($sourceSize/1KB, 2)) KB)" -ForegroundColor Green
            } else {
                Write-Host "⚠️ $file - 大小不匹配 (源: $([math]::Round($sourceSize/1KB, 2)) KB, 目标: $([math]::Round($targetSize/1KB, 2)) KB)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "❌ $file - 目标文件不存在" -ForegroundColor Red
        }
    } else {
        Write-Host "⚠️ $file - 源文件不存在" -ForegroundColor Yellow
    }
}

# 生成同步报告
$reportFile = "$sourceDir\IMMEDIATE_SYNC_REPORT_$(Get-Date -Format 'yyyyMMdd_HHmmss').md"
$reportContent = @"
# 🚀 立即同步到副脑03报告

## 📊 同步摘要
- **同步时间**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- **源目录**: $sourceDir
- **目标目录**: $targetDir
- **源文件数**: $sourceCount
- **目标文件数**: $targetCount
- **同步完成率**: $([math]::Round(($targetCount/$sourceCount)*100, 2))%

## 🔍 关键文件验证结果
"@

foreach ($file in $criticalFiles) {
    $sourcePath = Join-Path $sourceDir $file
    $targetPath = Join-Path $targetDir $file
    
    if (Test-Path $sourcePath) {
        if (Test-Path $targetPath) {
            $sourceSize = (Get-Item $sourcePath).Length
            $targetSize = (Get-Item $targetPath).Length
            
            if ($sourceSize -eq $targetSize) {
                $reportContent += "`n- ✅ **$file** - 同步成功 ($([math]::Round($sourceSize/1KB, 2)) KB)"
            } else {
                $reportContent += "`n- ⚠️ **$file** - 大小不匹配 (源: $([math]::Round($sourceSize/1KB, 2)) KB, 目标: $([math]::Round($targetSize/1KB, 2)) KB)"
            }
        } else {
            $reportContent += "`n- ❌ **$file** - 目标文件不存在"
        }
    } else {
        $reportContent += "`n- ⚠️ **$file** - 源文件不存在"
    }
}

$reportContent += @"

## 📁 目录结构
\`\`\`
$targetDir
$(Get-ChildItem -Path $targetDir -Depth 1 | ForEach-Object { "├── $($_.Name)" })
\`\`\`

## 🎯 副脑03立即可以执行
1. **启动网站**: \`node server-clean-fixed.js\`
2. **访问后台**: \`http://localhost:3000/share-system/dashboard.html\`
3. **测试页面**: 首页、工具页、登录页、注册页
4. **验证API**: 数据库API接口

## 📋 验证清单
- [ ] 网站服务启动正常
- [ ] 所有页面可访问
- [ ] 数据库功能正常
- [ ] API接口响应正常
- [ ] 后台管理系统可用

---
**同步日志**: $logFile
**生成时间**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@

Set-Content -Path $reportFile -Value $reportContent

Write-Host ""
Write-Host "📄 同步报告已生成: $reportFile" -ForegroundColor Cyan
Write-Host "📋 同步日志: $logFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "🎉 立即同步完成！" -ForegroundColor Green
Write-Host "副脑03现在可以启动最新版本的网站服务。" -ForegroundColor Green
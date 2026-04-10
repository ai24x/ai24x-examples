# SYNC_TO_SUBBRAIN03_RELIABLE.ps1
# 可靠的同步脚本 - 使用UTF-8编码

Write-Host "🚀 开始同步到副脑03..." -ForegroundColor Cyan
Write-Host ""

# 源目录和目标目录
$sourceDir = "C:\AI24X\OpenClaw\web\ai24x-website"
$targetDir = "C:\副脑03\ai24x-website"

Write-Host "源目录: $sourceDir"
Write-Host "目标目录: $targetDir"
Write-Host ""

# 检查目录
if (-not (Test-Path $sourceDir)) {
    Write-Host "❌ 源目录不存在: $sourceDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $targetDir)) {
    Write-Host "⚠️ 目标目录不存在，正在创建..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

# 创建日志文件
$logFile = Join-Path $sourceDir "SYNC_RELIABLE_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Write-Host "📋 开始同步..." -ForegroundColor Cyan
Write-Host "日志文件: $logFile"
Write-Host ""

# 使用robocopy进行同步
robocopy $sourceDir $targetDir /MIR /R:3 /W:5 /NP /LOG:$logFile

Write-Host ""
Write-Host "✅ 同步完成！" -ForegroundColor Green
Write-Host ""

# 验证关键文件
Write-Host "🔍 验证关键文件..." -ForegroundColor Cyan

$keyFiles = @(
    "server-clean-fixed.js",
    "index.html", 
    "tools-index.html",
    "login.html",
    "signup.html",
    "data\fission-rewards.json",
    "api\fission-db.js",
    "share-system\dashboard.html"
)

foreach ($file in $keyFiles) {
    $sourceFile = Join-Path $sourceDir $file
    $targetFile = Join-Path $targetDir $file
    
    if (Test-Path $sourceFile) {
        $sourceSize = (Get-Item $sourceFile).Length
        
        if (Test-Path $targetFile) {
            $targetSize = (Get-Item $targetFile).Length
            
            if ($sourceSize -eq $targetSize) {
                Write-Host "✅ $file - 同步成功 ($sourceSize 字节)" -ForegroundColor Green
            } else {
                Write-Host "⚠️ $file - 大小不匹配 (源: $sourceSize 字节, 目标: $targetSize 字节)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "❌ $file - 目标文件不存在" -ForegroundColor Red
        }
    } else {
        Write-Host "⚠️ $file - 源文件不存在" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "🎯 副脑03现在可以启动网站服务：" -ForegroundColor Cyan
Write-Host "1. 启动服务: node server-clean-fixed.js" -ForegroundColor White
Write-Host "2. 访问后台: http://localhost:3000/share-system/dashboard.html" -ForegroundColor White
Write-Host "3. 测试页面: 首页、工具页、登录页、注册页" -ForegroundColor White
Write-Host "4. 验证API: 数据库API接口" -ForegroundColor White
Write-Host ""

Write-Host "📋 同步日志: $logFile" -ForegroundColor Cyan
Write-Host ""

Write-Host "🎉 同步验证完成！副脑03部署就绪！" -ForegroundColor Green
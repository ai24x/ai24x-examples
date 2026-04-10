# GITEE_DOWNLOAD_FOR_SUBBRAIN03.ps1
# 副脑03从Gitee下载最新代码的脚本

Write-Host "🚀 副脑03从Gitee下载最新代码..." -ForegroundColor Cyan
Write-Host ""

# 配置信息
$giteeRepo = "https://gitee.com/ai24x/ai24x-website.git"
$targetDir = "C:\副脑03\ai24x-website"
$logFile = "GITEE_DOWNLOAD_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Write-Host "📋 配置信息:" -ForegroundColor Cyan
Write-Host "Gitee仓库: $giteeRepo"
Write-Host "目标目录: $targetDir"
Write-Host "日志文件: $logFile"
Write-Host ""

# 检查Git是否安装
Write-Host "🔍 检查Git安装..." -ForegroundColor Cyan
$gitVersion = git --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Git未安装，请先安装Git" -ForegroundColor Red
    Write-Host "安装方法: choco install git -y" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Git已安装: $gitVersion" -ForegroundColor Green

# 检查目标目录
if (Test-Path $targetDir) {
    Write-Host "📁 目标目录已存在，检查是否为Git仓库..." -ForegroundColor Yellow
    
    # 检查是否已经是Git仓库
    $isGitRepo = Test-Path (Join-Path $targetDir ".git")
    
    if ($isGitRepo) {
        Write-Host "✅ 目标目录已经是Git仓库，执行拉取更新..." -ForegroundColor Green
        
        # 切换到目录并拉取最新代码
        Push-Location $targetDir
        git pull origin master 2>&1 | Tee-Object -FilePath $logFile
        Pop-Location
    } else {
        Write-Host "⚠️ 目标目录不是Git仓库，备份后重新克隆..." -ForegroundColor Yellow
        
        # 备份现有目录
        $backupDir = "$targetDir.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Write-Host "备份到: $backupDir"
        Move-Item $targetDir $backupDir -Force
        
        # 克隆仓库
        git clone $giteeRepo $targetDir 2>&1 | Tee-Object -FilePath $logFile
    }
} else {
    Write-Host "📁 目标目录不存在，直接克隆仓库..." -ForegroundColor Cyan
    git clone $giteeRepo $targetDir 2>&1 | Tee-Object -FilePath $logFile
}

Write-Host ""
Write-Host "✅ Gitee下载完成！" -ForegroundColor Green
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
    $targetFile = Join-Path $targetDir $file
    
    if (Test-Path $targetFile) {
        $fileSize = (Get-Item $targetFile).Length
        Write-Host "✅ $file - 存在 ($fileSize 字节)" -ForegroundColor Green
    } else {
        Write-Host "❌ $file - 不存在" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🎯 副脑03现在可以启动网站服务：" -ForegroundColor Cyan
Write-Host "1. 启动服务: node server-clean-fixed.js" -ForegroundColor White
Write-Host "2. 访问后台: http://localhost:3000/share-system/dashboard.html" -ForegroundColor White
Write-Host "3. 测试页面: 首页、工具页、登录页、注册页" -ForegroundColor White
Write-Host "4. 验证API: 数据库API接口" -ForegroundColor White
Write-Host ""

Write-Host "📋 下载日志: $logFile" -ForegroundColor Cyan
Write-Host ""

# 显示Git状态
if (Test-Path (Join-Path $targetDir ".git")) {
    Write-Host "📊 Git仓库状态:" -ForegroundColor Cyan
    Push-Location $targetDir
    git status --short
    git log --oneline -5
    Pop-Location
}

Write-Host ""
Write-Host "🎉 Gitee下载完成！副脑03部署就绪！" -ForegroundColor Green
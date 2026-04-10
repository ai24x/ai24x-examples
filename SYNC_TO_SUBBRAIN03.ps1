# 同步到副脑03脚本
# 将更新的程序文件和数据库同步到副脑03目录

Write-Host "=== AI24X网站同步到副脑03 ==="
Write-Host "时间: $(Get-Date)"
Write-Host "源目录: C:\AI24X\OpenClaw\web\ai24x-website"
Write-Host "目标目录: C:\副脑03\ai24x-website"

# 源目录和目标目录
$sourceDir = "C:\AI24X\OpenClaw\web\ai24x-website"
$targetDir = "C:\副脑03\ai24x-website"

# 确保目标目录存在
if (-not (Test-Path $targetDir)) {
    Write-Host "创建目标目录: $targetDir"
    New-Item -ItemType Directory -Path $targetDir -Force
}

# 1. 同步核心程序文件
Write-Host "`n1. 同步核心程序文件..."

$coreFiles = @(
    "server-clean-fixed.js",
    "server-clean-fixed-new.js",
    "server-optimized.js",
    "server-stable.js",
    "server-unified-perfect.js",
    "server-simple-unified.js",
    "server-perfect-local.js",
    "server-no-conflict.js",
    "server-enhanced.js",
    "server-clean.js",
    "server-3000-fixed.js",
    "server-3000.js",
    "server.js",
    "package.json",
    "package-lock.json",
    "membership-schema.json",
    "users.json"
)

foreach ($file in $coreFiles) {
    $sourcePath = Join-Path $sourceDir $file
    $targetPath = Join-Path $targetDir $file
    
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
        Write-Host "  ✓ 同步: $file"
    } else {
        Write-Host "  ✗ 不存在: $file"
    }
}

# 2. 同步数据库文件
Write-Host "`n2. 同步数据库文件..."

$dataDir = Join-Path $sourceDir "data"
$targetDataDir = Join-Path $targetDir "data"

if (Test-Path $dataDir) {
    if (-not (Test-Path $targetDataDir)) {
        New-Item -ItemType Directory -Path $targetDataDir -Force
    }
    
    $dataFiles = Get-ChildItem $dataDir -File
    foreach ($file in $dataFiles) {
        $sourcePath = $file.FullName
        $targetPath = Join-Path $targetDataDir $file.Name
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
        Write-Host "  ✓ 同步数据库: $($file.Name)"
    }
}

# 3. 同步API文件
Write-Host "`n3. 同步API文件..."

$apiDir = Join-Path $sourceDir "api"
$targetApiDir = Join-Path $targetDir "api"

if (Test-Path $apiDir) {
    if (-not (Test-Path $targetApiDir)) {
        New-Item -ItemType Directory -Path $targetApiDir -Force
    }
    
    $apiFiles = Get-ChildItem $apiDir -File
    foreach ($file in $apiFiles) {
        $sourcePath = $file.FullName
        $targetPath = Join-Path $targetApiDir $file.Name
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
        Write-Host "  ✓ 同步API: $($file.Name)"
    }
}

# 4. 同步后台管理系统
Write-Host "`n4. 同步后台管理系统..."

$shareSystemDir = Join-Path $sourceDir "share-system"
$targetShareSystemDir = Join-Path $targetDir "share-system"

if (Test-Path $shareSystemDir) {
    # 同步整个share-system目录
    Robocopy $shareSystemDir $targetShareSystemDir /E /R:1 /W:1 /NP /NDL /NFL
    Write-Host "  ✓ 同步后台管理系统"
}

# 5. 同步管理脚本
Write-Host "`n5. 同步管理脚本..."

$managementScripts = @(
    "manage-server.bat",
    "server-manager.bat",
    "website-manager.bat",
    "website-service-manager.bat",
    "auto-restart-server.bat",
    "start-server.bat",
    "INTELLIGENT_SYNC_SCRIPT.ps1",
    "SYNC_OPENCLAW_SAFE.ps1",
    "SYNC_VERIFICATION.ps1",
    "WEBSITE_FIRST_UPDATE.ps1",
    "SYNC_TO_SUBBRAIN03.ps1"
)

foreach ($script in $managementScripts) {
    $sourcePath = Join-Path $sourceDir $script
    $targetPath = Join-Path $targetDir $script
    
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
        Write-Host "  ✓ 同步脚本: $script"
    }
}

# 6. 同步HTML页面
Write-Host "`n6. 同步HTML页面..."

$htmlFiles = @(
    "index.html",
    "tools-index.html",
    "tools.html",
    "tools-fixed.html",
    "custom.html",
    "login.html",
    "signup.html",
    "tutorials\index.html"
)

foreach ($htmlFile in $htmlFiles) {
    $sourcePath = Join-Path $sourceDir $htmlFile
    $targetPath = Join-Path $targetDir $htmlFile
    
    if (Test-Path $sourcePath) {
        # 确保目标目录存在
        $targetParent = Split-Path $targetPath -Parent
        if (-not (Test-Path $targetParent)) {
            New-Item -ItemType Directory -Path $targetParent -Force
        }
        
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
        Write-Host "  ✓ 同步页面: $htmlFile"
    }
}

# 7. 同步CSS和JavaScript文件
Write-Host "`n7. 同步CSS和JavaScript文件..."

# 同步CSS目录
$cssDir = Join-Path $sourceDir "css"
$targetCssDir = Join-Path $targetDir "css"

if (Test-Path $cssDir) {
    if (-not (Test-Path $targetCssDir)) {
        New-Item -ItemType Directory -Path $targetCssDir -Force
    }
    Robocopy $cssDir $targetCssDir /E /R:1 /W:1 /NP /NDL /NFL
    Write-Host "  ✓ 同步CSS文件"
}

# 同步JS目录
$jsDir = Join-Path $sourceDir "js"
$targetJsDir = Join-Path $targetDir "js"

if (Test-Path $jsDir) {
    if (-not (Test-Path $targetJsDir)) {
        New-Item -ItemType Directory -Path $targetJsDir -Force
    }
    Robocopy $jsDir $targetJsDir /E /R:1 /W:1 /NP /NDL /NFL
    Write-Host "  ✓ 同步JavaScript文件"
}

# 8. 同步教程目录
Write-Host "`n8. 同步教程目录..."

$tutorialsDir = Join-Path $sourceDir "tutorials"
$targetTutorialsDir = Join-Path $targetDir "tutorials"

if (Test-Path $tutorialsDir) {
    Robocopy $tutorialsDir $targetTutorialsDir /E /R:1 /W:1 /NP /NDL /NFL
    Write-Host "  ✓ 同步教程目录"
}

# 9. 同步文档和报告
Write-Host "`n9. 同步文档和报告..."

$documents = @(
    "OPENCLAW_PROGRAM_UPDATE_GUIDE.md",
    "OPENCLAW_UPDATE_STANDARD_PROCESS.md",
    "UPDATE_QUICK_REFERENCE.md",
    "MIGRATION_STATUS_REPORT.md",
    "MIGRATION_TEST_REPORT.md",
    "MIGRATION_COMPARISON_REPORT.md",
    "GITEE_PUSH_REPORT_20260321.md",
    "GITEE_PUSH_IMPROVEMENT_PLAN.md",
    "WEBSITE_SERVICE_STATUS.md",
    "SERVICE-MANAGEMENT.md"
)

foreach ($doc in $documents) {
    $sourcePath = Join-Path $sourceDir $doc
    $targetPath = Join-Path $targetDir $doc
    
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
        Write-Host "  ✓ 同步文档: $doc"
    }
}

# 10. 验证同步结果
Write-Host "`n10. 验证同步结果..."

$sourceCount = (Get-ChildItem $sourceDir -Recurse -File).Count
$targetCount = (Get-ChildItem $targetDir -Recurse -File).Count

Write-Host "源目录文件数: $sourceCount"
Write-Host "目标目录文件数: $targetCount"

if ($targetCount -gt 0) {
    $syncPercentage = [math]::Round(($targetCount / $sourceCount) * 100, 2)
    Write-Host "同步完成率: $syncPercentage%"
    Write-Host "`n✅ 同步到副脑03完成！"
} else {
    Write-Host "`n❌ 同步失败，目标目录为空"
}

# 生成同步报告
$reportContent = @"
# 副脑03同步报告
## 同步时间: $(Get-Date)
## 源目录: $sourceDir
## 目标目录: $targetDir

## 同步统计:
- 源目录文件数: $sourceCount
- 目标目录文件数: $targetCount
- 同步完成率: $syncPercentage%

## 同步内容:
1. 核心程序文件: $(($coreFiles | Where-Object { Test-Path (Join-Path $sourceDir $_) }).Count) 个
2. 数据库文件: $(if (Test-Path $dataDir) { (Get-ChildItem $dataDir -File).Count } else { 0 }) 个
3. API文件: $(if (Test-Path $apiDir) { (Get-ChildItem $apiDir -File).Count } else { 0 }) 个
4. 后台管理系统: $(if (Test-Path $shareSystemDir) { '已同步' } else { '未同步' })
5. 管理脚本: $(($managementScripts | Where-Object { Test-Path (Join-Path $sourceDir $_) }).Count) 个
6. HTML页面: $(($htmlFiles | Where-Object { Test-Path (Join-Path $sourceDir $_) }).Count) 个
7. CSS/JS文件: $(if (Test-Path $cssDir) { '已同步' } else { '未同步' })
8. 教程目录: $(if (Test-Path $tutorialsDir) { '已同步' } else { '未同步' })
9. 文档报告: $(($documents | Where-Object { Test-Path (Join-Path $sourceDir $_) }).Count) 个

## 同步状态: ✅ 完成
"@

$reportPath = Join-Path $targetDir "SYNC_REPORT_$(Get-Date -Format 'yyyyMMdd_HHmmss').md"
$reportContent | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "`n📋 同步报告已保存到: $reportPath"

Write-Host "`n=== 同步完成 ==="
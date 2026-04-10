# 修复教程页面头部菜单 - 添加"实时排行"菜单项
# 执行: pwsh -File FIX_TUTORIAL_HEADER_MENU.ps1

$TutorialsDir = "C:\claw\bak\daily\20260324\ai24x-website\tutorials"
$BackupDir = "$TutorialsDir\backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# 创建备份目录
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

# 正确的头部菜单HTML（包含实时排行）
$CorrectHeaderMenu = @'
                <nav class="main-nav">
                    <ul>
                        <li><a href="/" class="nav-link"><i class="fas fa-home"></i> <span class="nav-text">首页</span></a></li>
                        <li><a href="/tools" class="nav-link"><i class="fas fa-tools"></i> <span class="nav-text">AI工具库</span></a></li>
                        <li><a href="/rankings" class="nav-link"><i class="fas fa-chart-bar"></i> <span class="nav-text">实时排行</span></a></li>
                        <li><a href="/tutorials" class="nav-link"><i class="fas fa-chart-line"></i> <span class="nav-text">热门教程</span></a></li>
                        <li><a href="/custom" class="nav-link"><i class="fas fa-cogs"></i> <span class="nav-text">定制开发</span></a></li>
                    </ul>
                </nav>
'@

# 错误的头部菜单HTML（缺少实时排行）
$WrongHeaderMenu1 = @'
                <nav class="main-nav">
                    <ul>
                        <li><a href="/" class="nav-link"><i class="fas fa-home"></i> <span class="nav-text">首页</span></a></li>
                        <li><a href="/tools" class="nav-link"><i class="fas fa-tools"></i> <span class="nav-text">AI工具库</span></a></li>
                        <li><a href="/tutorials" class="nav-link active"><i class="fas fa-chart-line"></i> <span class="nav-text">热门教程</span></a></li>
                        <li><a href="/custom" class="nav-link"><i class="fas fa-cogs"></i> <span class="nav-text">定制开发</span></a></li>
                    </ul>
                </nav>
'@

$WrongHeaderMenu2 = @'
                <nav class="main-nav">
                    <ul>
                        <li><a href="/" class="nav-link"><i class="fas fa-home"></i> <span class="nav-text">首页</span></a></li>
                        <li><a href="/tools" class="nav-link"><i class="fas fa-tools"></i> <span class="nav-text">AI工具库</span></a></li>
                        <li><a href="/tutorials" class="nav-link"><i class="fas fa-chart-line"></i> <span class="nav-text">热门教程</span></a></li>
                        <li><a href="/custom" class="nav-link"><i class="fas fa-cogs"></i> <span class="nav-text">定制开发</span></a></li>
                    </ul>
                </nav>
'@

Write-Host "开始修复教程页面头部菜单..." -ForegroundColor Green
Write-Host "教程目录: $TutorialsDir" -ForegroundColor Cyan
Write-Host "备份目录: $BackupDir" -ForegroundColor Cyan

# 获取所有教程HTML文件（排除index.html，因为它已经是正确的）
$TutorialFiles = Get-ChildItem -Path $TutorialsDir -Filter "*.html" -File | Where-Object { $_.Name -ne "index.html" }

$FixedCount = 0
$SkippedCount = 0

foreach ($File in $TutorialFiles) {
    Write-Host "`n处理文件: $($File.Name)" -ForegroundColor Yellow
    
    # 备份原文件
    $BackupPath = Join-Path $BackupDir $File.Name
    Copy-Item -Path $File.FullName -Destination $BackupPath
    
    # 读取文件内容
    $Content = Get-Content -Path $File.FullName -Raw
    
    # 检查是否需要修复
    if ($Content -match "实时排行") {
        Write-Host "  ✓ 已包含'实时排行'菜单，跳过" -ForegroundColor Green
        $SkippedCount++
        continue
    }
    
    # 尝试匹配错误的菜单并替换
    $NewContent = $Content
    
    # 替换第一种错误的菜单（有active类）
    if ($NewContent -match [regex]::Escape($WrongHeaderMenu1)) {
        Write-Host "  → 修复第一种错误菜单（有active类）" -ForegroundColor Cyan
        $NewContent = $NewContent -replace [regex]::Escape($WrongHeaderMenu1), $CorrectHeaderMenu
        $FixedCount++
    }
    # 替换第二种错误的菜单（没有active类）
    elseif ($NewContent -match [regex]::Escape($WrongHeaderMenu2)) {
        Write-Host "  → 修复第二种错误菜单（没有active类）" -ForegroundColor Cyan
        $NewContent = $NewContent -replace [regex]::Escape($WrongHeaderMenu2), $CorrectHeaderMenu
        $FixedCount++
    }
    else {
        Write-Host "  ⚠  未找到标准菜单结构，需要手动检查" -ForegroundColor Red
        
        # 尝试更灵活的匹配
        $MenuPattern = '<nav class="main-nav">[\s\S]*?</nav>'
        if ($NewContent -match $MenuPattern) {
            $FoundMenu = $Matches[0]
            Write-Host "  找到菜单结构，但格式不标准" -ForegroundColor Yellow
            
            # 检查是否包含实时排行
            if ($FoundMenu -notmatch "实时排行") {
                Write-Host "  → 尝试修复非标准菜单" -ForegroundColor Magenta
                
                # 在AI工具库和热门教程之间插入实时排行
                $FixedMenu = $FoundMenu -replace '(<li><a href="/tools"[^>]*>[\s\S]*?</li>)\s*(<li><a href="/tutorials"[^>]*>)', "`$1`n                        <li><a href=`"/rankings`" class=`"nav-link`"><i class=`"fas fa-chart-bar`"></i> <span class=`"nav-text`">实时排行</span></a></li>`n                        `$2"
                
                if ($FoundMenu -ne $FixedMenu) {
                    $NewContent = $NewContent -replace [regex]::Escape($FoundMenu), $FixedMenu
                    $FixedCount++
                    Write-Host "  ✓ 非标准菜单修复成功" -ForegroundColor Green
                }
                else {
                    Write-Host "  ✗ 非标准菜单修复失败" -ForegroundColor Red
                }
            }
        }
    }
    
    # 如果内容有变化，保存文件
    if ($NewContent -ne $Content) {
        Set-Content -Path $File.FullName -Value $NewContent -Encoding UTF8
        Write-Host "  ✓ 文件已更新" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠  文件未修改" -ForegroundColor Gray
    }
}

Write-Host "`n" + ("=" * 50) -ForegroundColor Cyan
Write-Host "修复完成！" -ForegroundColor Green
Write-Host "已修复文件数: $FixedCount" -ForegroundColor Yellow
Write-Host "跳过文件数: $SkippedCount" -ForegroundColor Yellow
Write-Host "备份文件位置: $BackupDir" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan

# 验证修复结果
Write-Host "`n验证修复结果：" -ForegroundColor Green
$CheckFiles = Get-ChildItem -Path $TutorialsDir -Filter "*.html" -File

foreach ($File in $CheckFiles) {
    $Content = Get-Content -Path $File.FullName -Raw
    $HasRankings = $Content -match "实时排行"
    
    if ($HasRankings) {
        Write-Host "  ✓ $($File.Name) - 包含'实时排行'菜单" -ForegroundColor Green
    }
    else {
        Write-Host "  ✗ $($File.Name) - 缺少'实时排行'菜单" -ForegroundColor Red
    }
}

Write-Host "`n修复脚本执行完成！" -ForegroundColor Green
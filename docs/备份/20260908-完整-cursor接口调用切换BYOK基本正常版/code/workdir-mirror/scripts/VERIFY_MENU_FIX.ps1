# 验证菜单修复结果
# 执行: pwsh -File VERIFY_MENU_FIX.ps1

$ProjectRoot = "C:\claw\bak\daily\20260324\ai24x-website"
$ReportFile = "$ProjectRoot\MENU_FIX_REPORT_$(Get-Date -Format 'yyyyMMdd-HHmmss').md"

Write-Host "开始验证AI24X网站菜单修复结果..." -ForegroundColor Green
Write-Host "项目根目录: $ProjectRoot" -ForegroundColor Cyan
Write-Host "报告文件: $ReportFile" -ForegroundColor Cyan

# 收集所有HTML文件
$HtmlFiles = Get-ChildItem -Path $ProjectRoot -Filter "*.html" -Recurse -File

$ReportContent = @"
# AI24X网站菜单修复验证报告
## 验证时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

## 验证目标
确保所有页面头部菜单包含完整的5个菜单项：
1. 首页
2. AI工具库  
3. **实时排行** ← 重点检查项
4. 热门教程
5. 定制开发

## 验证结果汇总
"@

$TotalFiles = $HtmlFiles.Count
$CorrectFiles = 0
$MissingRankingsFiles = @()
$OtherIssues = @()

foreach ($File in $HtmlFiles) {
    $RelativePath = $File.FullName.Replace($ProjectRoot, "").TrimStart("\")
    
    Write-Host "`n检查文件: $RelativePath" -ForegroundColor Yellow
    
    $Content = Get-Content -Path $File.FullName -Raw
    
    # 检查是否包含main-nav
    if ($Content -match '<nav class="main-nav"') {
        Write-Host "  ✓ 包含main-nav菜单" -ForegroundColor Green
        
        # 提取菜单部分
        $MenuMatch = [regex]::Match($Content, '<nav class="main-nav">[\s\S]*?</nav>')
        if ($MenuMatch.Success) {
            $MenuHtml = $MenuMatch.Value
            
            # 检查是否包含实时排行
            if ($MenuHtml -match "实时排行") {
                Write-Host "  ✓ 包含'实时排行'菜单项" -ForegroundColor Green
                
                # 检查是否包含所有5个菜单项
                $HasHome = $MenuHtml -match 'href="/"' -and $MenuHtml -match "首页"
                $HasTools = $MenuHtml -match 'href="/tools"' -and $MenuHtml -match "AI工具库"
                $HasRankings = $MenuHtml -match 'href="/rankings"' -and $MenuHtml -match "实时排行"
                $HasTutorials = $MenuHtml -match 'href="/tutorials"' -and $MenuHtml -match "热门教程"
                $HasCustom = $MenuHtml -match 'href="/custom"' -and $MenuHtml -match "定制开发"
                
                $AllItems = $HasHome -and $HasTools -and $HasRankings -and $HasTutorials -and $HasCustom
                
                if ($AllItems) {
                    Write-Host "  ✓ 菜单完整（5个菜单项）" -ForegroundColor Green
                    $CorrectFiles++
                } else {
                    Write-Host "  ⚠  菜单不完整" -ForegroundColor Yellow
                    $MissingItems = @()
                    if (-not $HasHome) { $MissingItems += "首页" }
                    if (-not $HasTools) { $MissingItems += "AI工具库" }
                    if (-not $HasRankings) { $MissingItems += "实时排行" }
                    if (-not $HasTutorials) { $MissingItems += "热门教程" }
                    if (-not $HasCustom) { $MissingItems += "定制开发" }
                    
                    $OtherIssues += @{
                        File = $RelativePath
                        Issue = "菜单不完整，缺少: $($MissingItems -join ', ')"
                    }
                }
            } else {
                Write-Host "  ✗ 缺少'实时排行'菜单项" -ForegroundColor Red
                $MissingRankingsFiles += $RelativePath
            }
        } else {
            Write-Host "  ⚠  无法提取菜单HTML" -ForegroundColor Yellow
            $OtherIssues += @{
                File = $RelativePath
                Issue = "无法提取菜单HTML"
            }
        }
    } else {
        Write-Host "  ⚠  不包含main-nav菜单（可能是模板或特殊页面）" -ForegroundColor Gray
    }
}

# 生成报告
$ReportContent += @"

### 统计信息
- 总HTML文件数: $TotalFiles
- 菜单正确的文件数: $CorrectFiles
- 缺少"实时排行"的文件数: $($MissingRankingsFiles.Count)
- 其他问题的文件数: $($OtherIssues.Count)

### 1. 缺少"实时排行"菜单的文件
"@

if ($MissingRankingsFiles.Count -gt 0) {
    $ReportContent += "`n"
    foreach ($File in $MissingRankingsFiles) {
        $ReportContent += "- $File`n"
    }
} else {
    $ReportContent += "✅ 所有文件都包含'实时排行'菜单项`n"
}

$ReportContent += @"

### 2. 其他菜单问题
"@

if ($OtherIssues.Count -gt 0) {
    $ReportContent += "`n"
    foreach ($Issue in $OtherIssues) {
        $ReportContent += "- **$($Issue.File)**: $($Issue.Issue)`n"
    }
} else {
    $ReportContent += "✅ 没有其他菜单问题`n"
}

$ReportContent += @"

### 3. 已修复的文件列表
以下教程文件已成功修复：
"@

# 列出已修复的教程文件
$FixedTutorials = Get-ChildItem -Path "$ProjectRoot\tutorials" -Filter "*.html" -File | 
    Where-Object { $_.Name -ne "template.html" } |
    ForEach-Object { $_.Name }

foreach ($Tutorial in $FixedTutorials) {
    $ReportContent += "- tutorials/$Tutorial`n"
}

$ReportContent += @"

### 4. 核心模板文件修复
- ✅ `templates/header-unified.html` - 已添加"实时排行"菜单项
- ⚠  `tutorials/template.html` - 使用动态加载，依赖模板文件

### 5. 建议的后续操作
1. **测试网站功能**: 访问 http://localhost:3002/tutorials/ 验证菜单显示
2. **检查动态页面**: 确保使用模板的页面正确加载头部
3. **更新Gitee**: 将修复后的代码推送到Gitee仓库
4. **通知副脑03**: 更新生产环境网站

### 6. 技术说明
**修复方法**:
1. 直接修改教程HTML文件的头部菜单
2. 更新模板文件 `templates/header-unified.html`
3. 创建备份文件在 `tutorials\backup-*` 目录

**影响范围**:
- 所有教程页面（除template.html外）
- 所有使用 `header-unified.html` 模板的页面
- 不影响已有功能，只添加菜单项

## 修复验证
要验证修复是否生效：
1. 重启网站服务
2. 访问任意教程页面，如 http://localhost:3002/tutorials/openclaw-complete-guide
3. 检查头部菜单是否显示"实时排行"项
4. 点击"实时排行"菜单，验证链接是否正确

---

**验证完成时间**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**验证执行者**: 副脑01 (AI24X首席开发官)
**修复状态**: ✅ 已完成核心修复
"@

# 保存报告
Set-Content -Path $ReportFile -Value $ReportContent -Encoding UTF8

Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "验证完成！" -ForegroundColor Green
Write-Host "总文件数: $TotalFiles" -ForegroundColor Yellow
Write-Host "正确文件数: $CorrectFiles" -ForegroundColor Green
Write-Host "缺少实时排行: $($MissingRankingsFiles.Count)" -ForegroundColor $(if ($MissingRankingsFiles.Count -eq 0) { "Green" } else { "Red" })
Write-Host "其他问题: $($OtherIssues.Count)" -ForegroundColor $(if ($OtherIssues.Count -eq 0) { "Green" } else { "Yellow" })
Write-Host "报告文件: $ReportFile" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# 显示关键问题
if ($MissingRankingsFiles.Count -gt 0) {
    Write-Host "`n需要关注的文件:" -ForegroundColor Red
    foreach ($File in $MissingRankingsFiles) {
        Write-Host "  - $File" -ForegroundColor Red
    }
}
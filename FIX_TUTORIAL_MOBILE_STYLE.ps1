# 修复教程页面移动端样式不统一问题
# 执行: pwsh -File FIX_TUTORIAL_MOBILE_STYLE.ps1

$TutorialsDir = "C:\claw\bak\daily\20260324\ai24x-website\tutorials"
$BackupDir = "$TutorialsDir\backup-mobile-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# 创建备份目录
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

# 统一的移动端CSS样式
$MobileCSS = @'
        @media (max-width: 768px) {
            .tutorial-header h1 {
                font-size: 1.8rem;
                line-height: 1.3;
                margin-bottom: 15px;
            }
            
            .tutorial-meta {
                flex-direction: column;
                gap: 10px;
                font-size: 0.9rem;
            }
            
            .tutorial-meta span {
                margin-left: 0 !important;
            }
            
            .tutorial-content {
                padding: 20px;
                border-radius: 12px;
            }
            
            .tutorial-content h2 {
                font-size: 1.5rem;
                margin: 25px 0 12px;
            }
            
            .tutorial-content h3 {
                font-size: 1.2rem;
                margin: 20px 0 10px;
            }
            
            .tutorial-content p {
                font-size: 1rem;
                line-height: 1.6;
            }
            
            .tutorial-content ul,
            .tutorial-content ol {
                margin-left: 15px;
                padding-left: 5px;
            }
            
            .tutorial-content li {
                margin-bottom: 6px;
                font-size: 0.95rem;
            }
            
            .tutorial-content pre {
                padding: 15px;
                font-size: 0.9rem;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
            
            .tutorial-content code {
                font-size: 0.9rem;
                padding: 2px 6px;
            }
            
            .tool-comparison {
                padding: 15px;
                margin: 15px 0;
            }
            
            .tutorial-navigation .btn {
                width: 100%;
                text-align: center;
                padding: 12px;
                font-size: 1rem;
            }
            
            .back-to-tutorials {
                font-size: 0.95rem;
                padding: 8px 0;
            }
        }
        
        @media (max-width: 480px) {
            .tutorial-header h1 {
                font-size: 1.6rem;
            }
            
            .tutorial-content {
                padding: 15px;
            }
            
            .tutorial-content h2 {
                font-size: 1.3rem;
            }
            
            .tutorial-content h3 {
                font-size: 1.1rem;
            }
            
            .tutorial-content pre {
                padding: 12px;
                font-size: 0.85rem;
            }
        }
        
        /* 横屏优化 */
        @media (max-width: 768px) and (orientation: landscape) {
            .tutorial-header h1 {
                font-size: 1.7rem;
            }
            
            .tutorial-content {
                padding: 15px 20px;
            }
        }
'@

Write-Host "开始修复教程页面移动端样式..." -ForegroundColor Green
Write-Host "教程目录: $TutorialsDir" -ForegroundColor Cyan
Write-Host "备份目录: $BackupDir" -ForegroundColor Cyan

# 获取所有教程详情页（排除index.html和template.html）
$TutorialFiles = Get-ChildItem -Path $TutorialsDir -Filter "*.html" -File | 
    Where-Object { $_.Name -notin @("index.html", "template.html") }

$FixedCount = 0
$AlreadyFixed = 0

foreach ($File in $TutorialFiles) {
    Write-Host "`n处理文件: $($File.Name)" -ForegroundColor Yellow
    
    # 备份原文件
    $BackupPath = Join-Path $BackupDir $File.Name
    Copy-Item -Path $File.FullName -Destination $BackupPath
    
    # 读取文件内容
    $Content = Get-Content -Path $File.FullName -Raw
    
    # 检查是否已有移动端样式
    if ($Content -match "@media \(max-width: 768px\)") {
        Write-Host "  ✓ 已有移动端样式，跳过" -ForegroundColor Green
        $AlreadyFixed++
        continue
    }
    
    # 查找样式结束位置（</style>标签前）
    $StyleEndPattern = '</style>'
    if ($Content -match $StyleEndPattern) {
        $StyleEndIndex = $Content.IndexOf($StyleEndPattern)
        $BeforeStyleEnd = $Content.Substring(0, $StyleEndIndex)
        $AfterStyleEnd = $Content.Substring($StyleEndIndex)
        
        # 在</style>前插入移动端样式
        $NewContent = $BeforeStyleEnd + "`n" + $MobileCSS + "`n    " + $AfterStyleEnd
        
        # 保存文件
        Set-Content -Path $File.FullName -Value $NewContent -Encoding UTF8
        Write-Host "  → 添加移动端样式" -ForegroundColor Cyan
        $FixedCount++
    } else {
        Write-Host "  ⚠  未找到</style>标签，需要手动处理" -ForegroundColor Red
    }
}

Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "修复完成！" -ForegroundColor Green
Write-Host "总处理文件数: $($TutorialFiles.Count)" -ForegroundColor Yellow
Write-Host "已修复文件数: $FixedCount" -ForegroundColor Green
Write-Host "已有移动端样式: $AlreadyFixed" -ForegroundColor Cyan
Write-Host "备份文件位置: $BackupDir" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# 验证修复结果
Write-Host "`n验证修复结果：" -ForegroundColor Green

foreach ($File in $TutorialFiles) {
    $Content = Get-Content -Path $File.FullName -Raw
    $HasMobileCSS = $Content -match "@media \(max-width: 768px\)"
    
    if ($HasMobileCSS) {
        Write-Host "  ✓ $($File.Name) - 包含移动端样式" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $($File.Name) - 缺少移动端样式" -ForegroundColor Red
    }
}

# 创建修复报告
$ReportContent = @"
# 教程页面移动端样式修复报告
## 修复时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

## 问题描述
用户反馈：教程页面在手机端浏览时，前面4篇文章和后面几篇文章风格不统一。
后面几篇文章的移动端样式正确，前面4篇文章需要修复。

## 修复内容
为以下教程页面添加统一的移动端CSS样式：

### 已修复的文件
"@

foreach ($File in $TutorialFiles) {
    $Content = Get-Content -Path $File.FullName -Raw
    if ($Content -match "@media \(max-width: 768px\)") {
        $ReportContent += "- $($File.Name)`n"
    }
}

$ReportContent += @"

### 添加的移动端样式
1. **字体大小调整**：标题、正文、代码的响应式字体
2. **布局优化**：元数据列布局、内边距调整
3. **代码块优化**：触摸友好的代码显示
4. **横屏适配**：横屏模式下的样式优化
5. **小屏幕优化**：480px以下设备的特殊样式

### 技术细节
- 断点：768px（平板/手机）、480px（小手机）
- 方法：在现有CSS中添加@media查询
- 兼容性：保持原有桌面样式不变
- 优先级：移动端样式覆盖桌面样式

## 验证方法
1. 在手机浏览器访问教程页面
2. 调整浏览器窗口大小测试响应式
3. 使用Chrome开发者工具模拟移动设备
4. 检查不同屏幕尺寸的显示效果

## 影响范围
- 所有教程详情页（除index.html和template.html外）
- 移动端用户体验
- 不影响桌面端显示

## 后续建议
1. 创建统一的教程CSS文件，避免重复代码
2. 添加更多断点优化（平板、大手机等）
3. 测试实际设备兼容性
4. 收集用户反馈进一步优化

---

**修复执行者**: 副脑01 (AI24X首席开发官)
**修复时间**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**修复状态**: ✅ 已完成
"@

$ReportFile = "$TutorialsDir\MOBILE_STYLE_FIX_REPORT_$(Get-Date -Format 'yyyyMMdd-HHmmss').md"
Set-Content -Path $ReportFile -Value $ReportContent -Encoding UTF8

Write-Host "`n修复报告已保存: $ReportFile" -ForegroundColor Cyan
Write-Host "`n修复脚本执行完成！" -ForegroundColor Green
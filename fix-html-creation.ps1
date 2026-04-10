# 解决HTML文件创建卡死问题 - 简化版

Write-Host "🚀 开始解决HTML文件创建卡死问题..." -ForegroundColor Cyan

# 1. 检查内存
Write-Host "📊 检查系统内存..." -ForegroundColor Yellow
$mem = Get-WmiObject Win32_OperatingSystem
$freeGB = [math]::Round($mem.FreePhysicalMemory / 1MB, 1)
$totalGB = [math]::Round($mem.TotalVisibleMemorySize / 1MB, 1)
Write-Host "   可用内存: $freeGB GB / $totalGB GB" -ForegroundColor Green

# 2. 清理临时文件
Write-Host "🧹 清理临时文件..." -ForegroundColor Yellow
try {
    Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:TMP\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "   临时文件已清理" -ForegroundColor Green
} catch {
    Write-Host "   清理临时文件时出错: $_" -ForegroundColor Red
}

# 3. 创建HTML快速生成函数
Write-Host "🛠️ 创建HTML快速生成函数..." -ForegroundColor Yellow

$htmlFunc = @'
function New-FastHTML {
    param(
        [string]$File = "new-page.html",
        [string]$Title = "新页面",
        [string]$Content = "快速生成的HTML内容"
    )
    
    $html = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>$Title</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        h1 { color: #2c3e50; }
    </style>
</head>
<body>
    <h1>$Title</h1>
    <p>$Content</p>
    <p>生成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm')</p>
</body>
</html>
"@
    
    $html | Out-File -FilePath $File -Encoding UTF8
    Write-Host "✅ 已创建: $File" -ForegroundColor Green
}
'@

# 保存函数到文件
$htmlFunc | Out-File -FilePath "$env:USERPROFILE\Documents\New-FastHTML.ps1" -Encoding UTF8
Write-Host "   HTML生成函数已保存" -ForegroundColor Green

# 4. 创建测试文件
Write-Host "🧪 创建测试HTML文件..." -ForegroundColor Yellow
$testContent = @"
<!DOCTYPE html>
<html>
<head>
    <title>测试页面</title>
    <style>
        body { font-family: Arial; padding: 30px; }
        .success { color: green; font-size: 24px; }
    </style>
</head>
<body>
    <h1 class="success">✅ HTML文件创建测试</h1>
    <p>如果这个页面能正常打开，说明HTML创建功能正常。</p>
    <p>生成时间: $(Get-Date -Format 'HH:mm:ss')</p>
</body>
</html>
"@

$testContent | Out-File -FilePath "test-html.html" -Encoding UTF8
Write-Host "   测试文件已创建: test-html.html" -ForegroundColor Green

# 5. 优化建议
Write-Host "💡 优化建议:" -ForegroundColor Yellow
Write-Host @"
1. 使用命令行创建HTML文件（最快）:
   echo ^<!DOCTYPE html^> > page.html
   echo ^<html^> >> page.html
   echo ^<body^> >> page.html
   echo ^<h1^>标题^</h1^> >> page.html
   echo ^</body^> >> page.html
   echo ^</html^> >> page.html

2. 禁用编辑器自动格式化
3. 使用轻量级文本编辑器（Notepad++、Sublime Text）
4. 先创建小文件，再添加内容
5. 避免在浏览器中直接编辑大HTML文件
"@ -ForegroundColor White

Write-Host "🎉 优化完成！" -ForegroundColor Cyan
Write-Host "📁 HTML生成函数: $env:USERPROFILE\Documents\New-FastHTML.ps1" -ForegroundColor Yellow
Write-Host "💡 使用方法: . $env:USERPROFILE\Documents\New-FastHTML.ps1; New-FastHTML -File 'my.html' -Title '我的页面'" -ForegroundColor Yellow
# HTML文件创建优化脚本
# 解决HTML文件创建卡死问题

Write-Host "🚀 开始HTML文件创建优化..." -ForegroundColor Cyan

# 1. 检查系统资源
Write-Host "📊 检查系统资源..." -ForegroundColor Yellow
$memory = Get-CimInstance Win32_OperatingSystem
$freeMemoryGB = [math]::Round($memory.FreePhysicalMemory / 1MB, 2)
$totalMemoryGB = [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2)
Write-Host "   内存: $freeMemoryGB GB / $totalMemoryGB GB 可用" -ForegroundColor Green

# 2. 清理临时文件
Write-Host "🧹 清理临时文件..." -ForegroundColor Yellow
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:TMP\*" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "   临时文件已清理" -ForegroundColor Green

# 3. 优化文件系统
Write-Host "⚙️ 优化文件系统..." -ForegroundColor Yellow
fsutil behavior set memoryusage 2
fsutil behavior set disablelastaccess 1
Write-Host "   文件系统已优化" -ForegroundColor Green

# 4. 创建HTML模板工具
Write-Host "🛠️ 创建HTML快速生成工具..." -ForegroundColor Yellow

$htmlGenerator = @"
# HTML快速生成工具
function New-QuickHTML {
    param(
        [Parameter(Mandatory=\$true)]
        [string]\$Path,
        
        [string]\$Title = "新页面",
        [string]\$Content = "这是快速生成的HTML页面"
    )
    
    \$html = @"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>\$Title</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { 
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        p { margin-bottom: 15px; }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>\$Title</h1>
        <p>\$Content</p>
        <div class="footer">
            生成时间: \$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        </div>
    </div>
</body>
</html>
"@
    
    \$html | Out-File -FilePath \$Path -Encoding UTF8 -Force
    Write-Host "✅ HTML文件已创建: \$Path" -ForegroundColor Green
}

# 使用示例
# New-QuickHTML -Path "test.html" -Title "测试页面" -Content "这是测试内容"
"@

$htmlGenerator | Out-File -FilePath "$env:USERPROFILE\Documents\HTMLGenerator.ps1" -Encoding UTF8
Write-Host "   HTML生成工具已创建" -ForegroundColor Green

# 5. 浏览器优化建议
Write-Host "🌐 浏览器优化建议..." -ForegroundColor Yellow
Write-Host @"
   1. 禁用硬件加速:
      - Chrome: chrome://settings/system → 关闭'使用硬件加速'
      - Edge: edge://settings/system → 关闭'使用硬件加速'
   
   2. 清理浏览器缓存:
      - Chrome: Ctrl+Shift+Delete
      - Edge: Ctrl+Shift+Delete
   
   3. 使用开发者工具检查性能:
      - F12 → Performance tab
"@ -ForegroundColor White

# 6. 编辑器优化
Write-Host "📝 编辑器优化建议..." -ForegroundColor Yellow
Write-Host @"
   1. VS Code优化:
      - 禁用不必要的扩展
      - 设置: "files.autoSave": "off"
      - 设置: "editor.formatOnSave": false
   
   2. 使用轻量级编辑器:
      - Notepad++
      - Sublime Text
      - Vim/Nano (命令行)
   
   3. 文件操作技巧:
      - 先创建小文件，再逐步添加内容
      - 使用模板文件复制
      - 避免在浏览器中直接编辑大文件
"@ -ForegroundColor White

# 7. 系统性能优化
Write-Host "💻 系统性能优化..." -ForegroundColor Yellow

# 设置高性能电源计划
powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# 优化虚拟内存
$pagefile = Get-WmiObject Win32_PageFileSetting
if ($pagefile) {
    $pagefile.InitialSize = 4096
    $pagefile.MaximumSize = 8192
    $pagefile.Put()
}

Write-Host "   系统性能已优化" -ForegroundColor Green

# 8. 创建测试HTML文件
Write-Host "🧪 创建测试HTML文件..." -ForegroundColor Yellow
$testHTML = @"
<!DOCTYPE html>
<html>
<head>
    <title>性能测试</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        .success { color: green; font-weight: bold; }
    </style>
</head>
<body>
    <h1 class="success">✅ HTML文件创建测试成功！</h1>
    <p>生成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')</p>
    <p>内存使用: $freeMemoryGB GB 可用</p>
</body>
</html>
"@

$testHTML | Out-File -FilePath "C:\AI24X\OpenClaw\web\ai24x-website\test-performance.html" -Encoding UTF8
Write-Host "   测试文件已创建: test-performance.html" -ForegroundColor Green

Write-Host "🎉 HTML文件创建优化完成！" -ForegroundColor Cyan
Write-Host "📁 工具位置: $env:USERPROFILE\Documents\HTMLGenerator.ps1" -ForegroundColor Yellow
Write-Host "💡 使用方法: .\HTMLGenerator.ps1 然后调用 New-QuickHTML 函数" -ForegroundColor Yellow
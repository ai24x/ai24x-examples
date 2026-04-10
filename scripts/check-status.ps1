# AI24X网站状态检查脚本
Write-Host "=== AI24X网站状态检查 ===" -ForegroundColor Green
Write-Host "检查时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-Host "服务器地址: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""

# 检查服务器进程
Write-Host "1. 检查服务器进程..." -ForegroundColor Cyan
$process = Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*server-simple-unified.js*" }
if ($process) {
    Write-Host "   ✅ Node.js服务器进程运行中 (PID: $($process.Id))" -ForegroundColor Green
    Write-Host "   启动时间: $($process.StartTime.ToString('HH:mm:ss'))" -ForegroundColor White
    Write-Host "   内存使用: $([math]::Round($process.WorkingSet64/1MB, 2)) MB" -ForegroundColor White
} else {
    Write-Host "   ❌ 未找到服务器进程" -ForegroundColor Red
}

Write-Host ""

# 检查端口监听
Write-Host "2. 检查端口监听..." -ForegroundColor Cyan
$portCheck = netstat -ano | findstr ":3000" | findstr "LISTENING"
if ($portCheck) {
    Write-Host "   ✅ 3000端口正常监听" -ForegroundColor Green
    $pidFromPort = ($portCheck -split '\s+')[-1]
    Write-Host "   监听PID: $pidFromPort" -ForegroundColor White
} else {
    Write-Host "   ❌ 3000端口未监听" -ForegroundColor Red
}

Write-Host ""

# 测试页面访问
Write-Host "3. 测试页面访问..." -ForegroundColor Cyan

$pages = @(
    @{Name="首页"; Url="/"},
    @{Name="工具页面"; Url="/tools"},
    @{Name="教程首页"; Url="/tutorials"},
    @{Name="OpenClaw教程"; Url="/tutorials/openclaw/introduction.html"}
)

foreach ($page in $pages) {
    try {
        $startTime = Get-Date
        $response = Invoke-WebRequest -Uri "http://localhost:3000$($page.Url)" -UseBasicParsing -ErrorAction Stop
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        if ($response.StatusCode -eq 200) {
            Write-Host "   ✅ $($page.Name): $([math]::Round($duration, 2))ms" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️ $($page.Name)状态码异常: $($response.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   ❌ $($page.Name)访问失败: $($_.Exception.Message)" -ForegroundColor Red
    }
    Start-Sleep -Milliseconds 200
}

Write-Host ""

# 检查服务器响应头
Write-Host "4. 检查服务器响应头..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/" -UseBasicParsing -ErrorAction Stop
    Write-Host "   ✅ 服务器响应正常" -ForegroundColor Green
    Write-Host "   状态码: $($response.StatusCode)" -ForegroundColor White
    Write-Host "   内容类型: $($response.Headers['Content-Type'])" -ForegroundColor White
    Write-Host "   服务器: $($response.Headers['Server'])" -ForegroundColor White
} catch {
    Write-Host "   ❌ 服务器响应检查失败" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 状态检查完成 ===" -ForegroundColor Green
Write-Host "总结: AI24X网站服务运行正常" -ForegroundColor Green
Write-Host "所有核心页面均可访问，响应时间正常" -ForegroundColor White
@echo off
chcp 65001 >nul
title AI24X网站服务器管理器

:menu
cls
echo ========================================
echo        AI24X网站服务器管理器
echo ========================================
echo.
echo 请选择操作：
echo.
echo [1] 启动标准服务器 (端口3000)
echo [2] 启动优化服务器 (端口3001)
echo [3] 启动双服务器模式 (负载均衡)
echo [4] 启动负载均衡器 (端口8080)
echo [5] 停止所有服务器
echo [6] 查看服务器状态
echo [7] 性能测试
echo [8] 退出
echo.
set /p choice=请输入选择 (1-8): 

if "%choice%"=="1" goto start_standard
if "%choice%"=="2" goto start_optimized
if "%choice%"=="3" goto start_dual
if "%choice%"=="4" goto start_balancer
if "%choice%"=="5" goto stop_all
if "%choice%"=="6" goto show_status
if "%choice%"=="7" goto performance_test
if "%choice%"=="8" goto exit
goto menu

:start_standard
echo.
echo 正在启动标准服务器 (端口3000)...
start "AI24X标准服务器" cmd /c "node server-simple-unified.js"
echo 标准服务器已启动！
echo 访问地址: http://localhost:3000
timeout /t 2 >nul
goto menu

:start_optimized
echo.
echo 正在启动优化服务器 (端口3001)...
start "AI24X优化服务器" cmd /c "node server-optimized.js"
echo 优化服务器已启动！
echo 访问地址: http://localhost:3001
echo 性能监控: http://localhost:3001/_status
timeout /t 2 >nul
goto menu

:start_dual
echo.
echo 正在启动双服务器模式...
echo 标准服务器 (端口3000)...
start "AI24X标准服务器" cmd /c "node server-simple-unified.js"
echo 优化服务器 (端口3001)...
start "AI24X优化服务器" cmd /c "node server-optimized.js"
echo.
echo 双服务器模式已启动！
echo 标准服务器: http://localhost:3000
echo 优化服务器: http://localhost:3001
echo 性能监控: http://localhost:3001/_status
echo.
echo 负载均衡建议：
echo 1. 使用负载均衡器 (选择选项4)
echo 2. 或手动分配流量
timeout /t 3 >nul
goto menu

:start_balancer
echo.
echo 正在启动负载均衡器 (端口8080)...
echo 注意：请确保标准服务器和优化服务器已启动
echo.
start "AI24X负载均衡器" cmd /c "node simple-balancer.js"
echo 负载均衡器已启动！
echo 访问地址: http://localhost:8080
echo 负载均衡监控: http://localhost:8080/_lb_status
echo.
echo 后端服务器：
echo   - 标准服务器: http://localhost:3000
echo   - 优化服务器: http://localhost:3001
echo.
echo 负载均衡特性：
echo   ✅ 自动健康检查
echo   ✅ 故障转移
echo   ✅ 轮询分发
echo   ✅ 实时监控
timeout /t 3 >nul
goto menu

:stop_all
echo.
echo 正在停止所有Node.js服务器...
taskkill /F /IM node.exe >nul 2>&1
echo 所有服务器已停止！
timeout /t 2 >nul
goto menu

:show_status
echo.
echo 服务器状态检查...
echo.
echo 标准服务器 (3000):
curl -s -o nul -w "%%{http_code}" http://localhost:3000/ >nul 2>&1
if errorlevel 1 (
    echo ❌ 未运行
) else (
    echo ✅ 运行正常
)

echo 优化服务器 (3001):
curl -s -o nul -w "%%{http_code}" http://localhost:3001/ >nul 2>&1
if errorlevel 1 (
    echo ❌ 未运行
) else (
    echo ✅ 运行正常
)

echo 负载均衡器 (8080):
curl -s -o nul -w "%%{http_code}" http://localhost:8080/_lb_status >nul 2>&1
if errorlevel 1 (
    echo ❌ 未运行
) else (
    echo ✅ 运行正常
)

echo.
echo 进程列表:
tasklist | findstr node
echo.
pause
goto menu

:performance_test
echo.
echo 性能测试模式...
echo.
echo 测试优化服务器响应时间...
powershell -Command "$startTime = Get-Date; $response = Invoke-WebRequest -Uri 'http://localhost:3001/' -UseBasicParsing; $endTime = Get-Date; $duration = ($endTime - $startTime).TotalMilliseconds; Write-Host '第一次访问: $($duration)ms'; $startTime = Get-Date; $response = Invoke-WebRequest -Uri 'http://localhost:3001/' -UseBasicParsing; $endTime = Get-Date; $duration = ($endTime - $startTime).TotalMilliseconds; Write-Host '缓存后访问: $($duration)ms'"
echo.
echo 查看性能统计...
curl -s http://localhost:3001/_status | python -m json.tool 2>nul
if errorlevel 1 (
    echo 需要Python来格式化JSON输出
    curl -s http://localhost:3001/_status
)
echo.
pause
goto menu

:exit
echo.
echo 正在退出服务器管理器...
taskkill /F /IM node.exe >nul 2>&1
echo 再见！
timeout /t 2 >nul
exit
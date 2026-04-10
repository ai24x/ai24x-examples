@echo off
chcp 65001 >nul
title AI24X超级守护进程监控工具

:menu
cls
echo.
echo ========================================
echo AI24X超级守护进程监控工具
echo 三重保障机制监控和管理
echo ========================================
echo.
echo 1. 启动超级守护进程 (三重保障)
echo 2. 停止超级守护进程
echo 3. 重启超级守护进程
echo 4. 查看实时状态
echo 5. 查看监控日志
echo 6. 查看资源使用
echo 7. 测试网站健康
echo 8. 清理系统资源
echo 9. 退出
echo.
set /p choice=请选择操作 (1-9): 

if "%choice%"=="1" goto start_super
if "%choice%"=="2" goto stop_super
if "%choice%"=="3" goto restart_super
if "%choice%"=="4" goto status
if "%choice%"=="5" goto view_log
if "%choice%"=="6" goto view_resources
if "%choice%"=="7" goto test_health
if "%choice%"=="8" goto cleanup
if "%choice%"=="9" goto exit
goto menu

:start_super
cls
echo.
echo 🚀 启动超级守护进程 (三重保障机制)...
call start-super-daemon.bat
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:stop_super
cls
echo.
echo 🛑 停止超级守护进程...
if exist super-daemon.pid (
    for /f "usebackq delims=" %%i in ("super-daemon.pid") do set "PID=%%i"
    tasklist /FI "PID eq %PID%" 2>nul | findstr /i "node.exe" >nul
    if %errorlevel% equ 0 (
        echo 发送优雅关闭信号...
        taskkill /PID %PID% >nul 2>nul
        timeout /t 5 /nobreak >nul
        
        tasklist /FI "PID eq %PID%" 2>nul | findstr /i "node.exe" >nul
        if %errorlevel% equ 0 (
            echo 进程未响应，强制终止...
            taskkill /PID %PID% /F >nul 2>nul
        )
        
        echo ✅ 已停止超级守护进程 (PID: %PID%)
        del super-daemon.pid >nul 2>nul
        if exist super-daemon-status.json del super-daemon-status.json >nul 2>nul
    ) else (
        echo ℹ️ 超级守护进程未运行
        del super-daemon.pid >nul 2>nul
        if exist super-daemon-status.json del super-daemon-status.json >nul 2>nul
    )
) else (
    echo ℹ️ 未找到超级守护进程PID文件
)
echo.
echo 清理所有node进程...
taskkill /F /IM node.exe >nul 2>nul
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:restart_super
cls
echo.
echo 🔄 重启超级守护进程...
call :stop_super >nul
timeout /t 3 /nobreak >nul
call :start_super >nul
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:status
cls
echo.
echo 📊 超级守护进程状态检查...
echo.
echo 1. 进程状态:
if exist super-daemon.pid (
    for /f "usebackq delims=" %%i in ("super-daemon.pid") do set "PID=%%i"
    tasklist /FI "PID eq %PID%" 2>nul | findstr /i "node.exe" >nul
    if %errorlevel% equ 0 (
        echo ✅ 超级守护进程运行中 (PID: %PID%)
    ) else (
        echo ❌ 超级守护进程未运行 (PID文件存在但进程不存在)
    )
) else (
    echo ❌ 超级守护进程未运行
)

echo.
echo 2. 状态文件信息:
if exist super-daemon-status.json (
    echo ✅ 状态文件存在
    for /f "tokens=2 delims=:" %%i in ('findstr "startTime" super-daemon-status.json') do set "startTime=%%i"
    for /f "tokens=2 delims=:" %%i in ('findstr "restartCount" super-daemon-status.json') do set "restartCount=%%i"
    for /f "tokens=2 delims=:" %%i in ('findstr "consecutiveFailures" super-daemon-status.json') do set "failures=%%i"
    
    echo   启动时间: %startTime%
    echo   重启次数: %restartCount%
    echo   连续失败: %failures%
) else (
    echo ❌ 状态文件不存在
)

echo.
echo 3. 网站服务器状态:
curl -s -o nul -w "%%{http_code}" http://localhost:3000/health 2>nul
if %errorlevel% equ 0 (
    echo ✅ 网站服务器运行正常
    echo   访问地址: http://localhost:3000
    echo   健康检查: http://localhost:3000/health
    echo   状态监控: http://localhost:3000/status
    
    echo.
    echo 4. 实时健康检查:
    curl -s http://localhost:3000/health | findstr "status uptime memory"
) else (
    echo ❌ 网站服务器未响应
)

echo.
echo 5. 系统资源:
wmic process where "name='node.exe'" get ProcessId,WorkingSetSize,Name /format:csv 2>nul | findstr /v "Node" | findstr "[0-9]"
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:view_log
cls
echo.
echo 📝 超级守护进程日志 (最后100行):
echo ========================================
if exist super-daemon.log (
    for /f "skip=0" %%i in ('find /c /v "" ^< super-daemon.log') do set /a lines=%%i
    set /a startline=lines-100
    if !startline! lss 1 set startline=1
    more +!startline! super-daemon.log
) else (
    echo ℹ️ 未找到超级守护进程日志文件
)
echo ========================================
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:view_resources
cls
echo.
echo 💾 系统资源监控...
echo.
echo 1. 内存使用情况:
wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /format:csv 2>nul | findstr /v "Node"
echo.
echo 2. CPU使用情况:
wmic cpu get LoadPercentage /format:csv 2>nul | findstr /v "Node"
echo.
echo 3. 磁盘空间:
wmic logicaldisk where "drivetype=3" get DeviceID,Size,FreeSpace /format:csv 2>nul | findstr /v "Node"
echo.
echo 4. 网络连接:
netstat -an | findstr ":3000"
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:test_health
cls
echo.
echo 🏥 网站健康测试 (三重测试)...
echo.
echo 测试1: 快速健康检查 (3次)
for /l %%i in (1,1,3) do (
    echo 检查 %%i/3:
    curl -s -w "   状态: %%{http_code}, 响应时间: %%{time_total}秒\\n" http://localhost:3000/health
    timeout /t 1 /nobreak >nul
)

echo.
echo 测试2: 页面访问测试
echo 首页: 
curl -s -o nul -w "   状态: %%{http_code}, 大小: %%{size_download}字节, 时间: %%{time_total}秒\\n" http://localhost:3000
echo 工具库: 
curl -s -o nul -w "   状态: %%{http_code}, 大小: %%{size_download}字节, 时间: %%{time_total}秒\\n" http://localhost:3000/tools
echo 状态页: 
curl -s -o nul -w "   状态: %%{http_code}, 大小: %%{size_download}字节, 时间: %%{time_total}秒\\n" http://localhost:3000/status

echo.
echo 测试3: 压力测试 (连续10次请求)
setlocal enabledelayedexpansion
set total_time=0
for /l %%i in (1,1,10) do (
    for /f "tokens=*" %%t in ('curl -s -w "%%{time_total}" -o nul http://localhost:3000/health') do set "response_time=%%t"
    set /a total_time=!total_time! + !response_time! * 1000
    echo 请求 %%i: !response_time!秒
    timeout /t 0.5 /nobreak >nul
)
set /a avg_time=!total_time! / 10
echo.
echo ✅ 压力测试完成
echo 平均响应时间: !avg_time!毫秒
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:cleanup
cls
echo.
echo 🧹 系统资源清理...
echo.
echo 1. 清理临时文件...
del /Q *.tmp 2>nul
del /Q *.temp 2>nul
echo ✅ 临时文件已清理
echo.
echo 2. 清理旧的日志文件 (保留最近3天)...
forfiles /p . /m "*.log" /d -3 /c "cmd /c del @file"
echo ✅ 旧日志文件已清理
echo.
echo 3. 清理node进程缓存...
del /Q node_modules\.cache\* 2>nul
echo ✅ node缓存已清理
echo.
echo 4. 重启网络服务...
netsh int ip reset >nul 2>nul
netsh winsock reset >nul 2>nul
echo ✅ 网络服务已重置
echo.
echo 🎉 系统资源清理完成！
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:exit
cls
echo.
echo 👋 感谢使用AI24X超级守护进程监控工具
echo.
timeout /t 2 /nobreak >nul
exit /b 0
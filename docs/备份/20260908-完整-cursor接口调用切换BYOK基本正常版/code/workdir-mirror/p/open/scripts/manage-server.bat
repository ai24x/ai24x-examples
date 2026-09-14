@echo off
chcp 65001 >nul
title AI24X网站服务器管理工具

:menu
cls
echo.
echo ========================================
echo AI24X网站服务器管理工具
echo ========================================
echo.
echo 1. 启动守护进程 (确保永远在线)
echo 2. 停止守护进程
echo 3. 重启守护进程
echo 4. 查看服务器状态
echo 5. 查看守护进程日志
echo 6. 查看服务器日志
echo 7. 测试网站访问
echo 8. 健康检查
echo 9. 退出
echo.
set /p choice=请选择操作 (1-9): 

if "%choice%"=="1" goto start_daemon
if "%choice%"=="2" goto stop_daemon
if "%choice%"=="3" goto restart_daemon
if "%choice%"=="4" goto status
if "%choice%"=="5" goto view_daemon_log
if "%choice%"=="6" goto view_server_log
if "%choice%"=="7" goto test_website
if "%choice%"=="8" goto health_check
if "%choice%"=="9" goto exit
goto menu

:start_daemon
cls
echo.
echo 🚀 启动守护进程...
call start-daemon.bat
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:stop_daemon
cls
echo.
echo 🛑 停止守护进程...
if exist server-daemon.pid (
    for /f "usebackq delims=" %%i in ("server-daemon.pid") do set "PID=%%i"
    tasklist /FI "PID eq %PID%" 2>nul | findstr /i "node.exe" >nul
    if %errorlevel% equ 0 (
        taskkill /PID %PID% /F >nul 2>nul
        echo ✅ 已停止守护进程 (PID: %PID%)
        del server-daemon.pid >nul 2>nul
    ) else (
        echo ℹ️ 守护进程未运行
        del server-daemon.pid >nul 2>nul
    )
) else (
    echo ℹ️ 未找到守护进程PID文件
)
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:restart_daemon
cls
echo.
echo 🔄 重启守护进程...
if exist server-daemon.pid (
    for /f "usebackq delims=" %%i in ("server-daemon.pid") do set "PID=%%i"
    tasklist /FI "PID eq %PID%" 2>nul | findstr /i "node.exe" >nul
    if %errorlevel% equ 0 (
        taskkill /PID %PID% /F >nul 2>nul
        echo ✅ 已停止现有守护进程
        timeout /t 2 /nobreak >nul
    )
    del server-daemon.pid >nul 2>nul
)
call start-daemon.bat
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:status
cls
echo.
echo 📊 服务器状态检查...
echo.
echo 1. 守护进程状态:
if exist server-daemon.pid (
    for /f "usebackq delims=" %%i in ("server-daemon.pid") do set "PID=%%i"
    tasklist /FI "PID eq %PID%" 2>nul | findstr /i "node.exe" >nul
    if %errorlevel% equ 0 (
        echo ✅ 守护进程运行中 (PID: %PID%)
    ) else (
        echo ❌ 守护进程未运行 (PID文件存在但进程不存在)
    )
) else (
    echo ❌ 守护进程未运行
)

echo.
echo 2. 网站服务器状态:
curl -s -o nul -w "%%{http_code}" http://localhost:3000/health 2>nul
if %errorlevel% equ 0 (
    echo ✅ 网站服务器运行正常
    echo   访问地址: http://localhost:3000
    echo   健康检查: http://localhost:3000/health
) else (
    echo ❌ 网站服务器未响应
)

echo.
echo 3. 内存使用情况:
wmic process where "name='node.exe'" get ProcessId,WorkingSetSize /format:csv 2>nul | findstr /v "Node" | findstr "[0-9]"
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:view_daemon_log
cls
echo.
echo 📝 守护进程日志 (最后50行):
echo ========================================
if exist server-daemon.log (
    for /f "skip=0" %%i in ('find /c /v "" ^< server-daemon.log') do set /a lines=%%i
    set /a startline=lines-50
    if !startline! lss 1 set startline=1
    more +!startline! server-daemon.log
) else (
    echo ℹ️ 未找到守护进程日志文件
)
echo ========================================
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:view_server_log
cls
echo.
echo 📝 服务器日志:
echo ========================================
if exist server.log (
    type server.log
) else (
    echo ℹ️ 未找到服务器日志文件
)
echo ========================================
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:test_website
cls
echo.
echo 🌐 测试网站访问...
echo.
echo 1. 测试首页访问:
curl -s -o test-homepage.html -w "状态码: %%{http_code}, 大小: %%{size_download}字节, 时间: %%{time_total}秒\\n" http://localhost:3000
echo.
echo 2. 测试工具库页面:
curl -s -o test-tools.html -w "状态码: %%{http_code}, 大小: %%{size_download}字节, 时间: %%{time_total}秒\\n" http://localhost:3000/tools
echo.
echo 3. 测试健康检查:
curl -s http://localhost:3000/health
echo.
echo.
echo ✅ 测试完成
del test-homepage.html >nul 2>nul
del test-tools.html >nul 2>nul
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:health_check
cls
echo.
echo 🏥 健康检查...
echo.
for /l %%i in (1,1,5) do (
    echo 检查 %%i/5:
    curl -s -w "  状态: %%{http_code}, 响应时间: %%{time_total}秒\\n" http://localhost:3000/health
    timeout /t 1 /nobreak >nul
)
echo.
echo ✅ 健康检查完成
echo.
echo 按任意键返回菜单...
pause >nul
goto menu

:exit
cls
echo.
echo 👋 感谢使用AI24X网站服务器管理工具
echo.
timeout /t 2 /nobreak >nul
exit /b 0
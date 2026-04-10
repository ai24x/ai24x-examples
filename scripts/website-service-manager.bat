@echo off
chcp 65001 >nul
title AI24X网站服务管理器

:menu
cls
echo ==========================================
echo        AI24X网站服务管理器
echo ==========================================
echo 当前时间: %date% %time%
echo 项目目录: %cd%
echo ==========================================
echo.
echo 请选择操作:
echo.
echo   [1] 启动网站服务
echo   [2] 停止网站服务
echo   [3] 重启网站服务
echo   [4] 查看服务状态
echo   [5] 测试网站访问
echo   [6] 查看服务器日志
echo   [7] 打开网站首页
echo   [8] 打开工具页面
echo   [9] 打开教程页面
echo   [0] 退出
echo.
echo ==========================================
set /p choice="请选择 (0-9): "

if "%choice%"=="1" goto start_service
if "%choice%"=="2" goto stop_service
if "%choice%"=="3" goto restart_service
if "%choice%"=="4" goto check_status
if "%choice%"=="5" goto test_access
if "%choice%"=="6" goto view_logs
if "%choice%"=="7" goto open_home
if "%choice%"=="8" goto open_tools
if "%choice%"=="9" goto open_tutorials
if "%choice%"=="0" goto exit_program

echo 无效选择，请重新输入
pause
goto menu

:start_service
echo.
echo ==========================================
echo 正在启动AI24X网站服务...
echo ==========================================
echo.

REM 检查端口是否被占用
netstat -ano | findstr :3000 >nul
if %errorlevel% equ 0 (
    echo 端口3000已被占用，正在清理...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
        echo 停止进程PID: %%a
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

REM 启动服务器
echo 启动服务器: server-clean-fixed.js
start "AI24X网站服务" cmd /c "node server-clean-fixed.js"
echo.
echo ✅ 网站服务已启动
echo 访问地址: http://localhost:3000
echo.
pause
goto menu

:stop_service
echo.
echo ==========================================
echo 正在停止AI24X网站服务...
echo ==========================================
echo.

REM 停止所有Node.js进程
taskkill /F /IM node.exe >nul 2>&1
echo ✅ 已停止所有Node.js进程
echo.
pause
goto menu

:restart_service
echo.
echo ==========================================
echo 正在重启AI24X网站服务...
echo ==========================================
echo.

REM 先停止服务
call :stop_service
timeout /t 2 /nobreak >nul

REM 再启动服务
call :start_service
goto menu

:check_status
echo.
echo ==========================================
echo 检查网站服务状态
echo ==========================================
echo.

REM 检查进程
tasklist /FI "IMAGENAME eq node.exe" 2>nul | findstr /I node.exe >nul
if %errorlevel% equ 0 (
    echo ✅ Node.js进程正在运行
    echo.
    echo 进程信息:
    tasklist /FI "IMAGENAME eq node.exe" /FO TABLE
) else (
    echo ❌ Node.js进程未运行
)

echo.
REM 检查端口
netstat -ano | findstr :3000 >nul
if %errorlevel% equ 0 (
    echo ✅ 端口3000正在监听
    echo.
    echo 端口信息:
    netstat -ano | findstr :3000
) else (
    echo ❌ 端口3000未监听
)

echo.
pause
goto menu

:test_access
echo.
echo ==========================================
echo 测试网站访问
echo ==========================================
echo.

echo 正在测试网站访问...
echo.

REM 测试首页
curl -s -o nul -w "首页: %%{http_code}\n" http://localhost:3000/
if %errorlevel% neq 0 echo 首页: 访问失败

REM 测试工具页面
curl -s -o nul -w "工具页面: %%{http_code}\n" http://localhost:3000/tools
if %errorlevel% neq 0 echo 工具页面: 访问失败

REM 测试教程页面
curl -s -o nul -w "教程页面: %%{http_code}\n" http://localhost:3000/tutorials
if %errorlevel% neq 0 echo 教程页面: 访问失败

echo.
pause
goto menu

:view_logs
echo.
echo ==========================================
echo 查看服务器日志
echo ==========================================
echo.

echo 服务器日志将显示在控制台窗口中...
echo 按Ctrl+C停止查看日志
echo.
echo 正在查看服务器日志...
echo.

REM 这里需要手动查看，因为服务器在后台运行
echo 请查看启动服务器的控制台窗口
echo.
pause
goto menu

:open_home
echo.
echo ==========================================
echo 打开网站首页
echo ==========================================
echo.

start http://localhost:3000/
echo ✅ 已打开浏览器访问首页
echo.
pause
goto menu

:open_tools
echo.
echo ==========================================
echo 打开工具页面
echo ==========================================
echo.

start http://localhost:3000/tools
echo ✅ 已打开浏览器访问工具页面
echo.
pause
goto menu

:open_tutorials
echo.
echo ==========================================
echo 打开教程页面
echo ==========================================
echo.

start http://localhost:3000/tutorials
echo ✅ 已打开浏览器访问教程页面
echo.
pause
goto menu

:exit_program
echo.
echo ==========================================
echo 感谢使用AI24X网站服务管理器
echo ==========================================
echo.
exit /b 0
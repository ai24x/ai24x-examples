@echo off
echo ========================================
echo AI24X网站永久在线服务启动脚本
echo 启动时间: %date% %time%
echo ========================================

REM 切换到网站目录
cd /d "C:\AI24X\OpenClaw\web\ai24x-website"

REM 检查是否已有node进程在运行
tasklist /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq AI24X*" 2>nul | find /I "node.exe" >nul
if %errorlevel% equ 0 (
    echo [INFO] AI24X网站已在运行，跳过启动
    goto :end
)

REM 启动网站服务器
echo [INFO] 启动AI24X网站服务器...
start "AI24X Website Server" /MIN node server.js

REM 等待服务器启动
timeout /t 5 /nobreak >nul

REM 检查服务器是否成功启动
curl -s http://localhost:3000/health >nul
if %errorlevel% equ 0 (
    echo [SUCCESS] AI24X网站服务器启动成功！
    echo [INFO] 访问地址: http://localhost:3000
    echo [INFO] 健康检查: http://localhost:3000/health
) else (
    echo [ERROR] AI24X网站服务器启动失败！
    echo [INFO] 尝试使用守护进程启动...
    
    REM 尝试使用守护进程启动
    start "AI24X Website Daemon" /MIN node super-daemon.js
    
    REM 再次检查
    timeout /t 10 /nobreak >nul
    curl -s http://localhost:3000/health >nul
    if %errorlevel% equ 0 (
        echo [SUCCESS] AI24X网站守护进程启动成功！
    ) else (
        echo [ERROR] 所有启动方式都失败，请手动检查！
    )
)

:end
echo ========================================
echo 脚本执行完成
echo ========================================
pause
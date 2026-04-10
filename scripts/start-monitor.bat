@echo off
chcp 65001 >nul
title AI24X网站监控服务
echo ========================================
echo      AI24X网站监控服务启动
echo ========================================
echo 时间: %date% %time%
echo 目录: %cd%
echo.

:: 检查Node.js是否安装
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到Node.js，请先安装Node.js
    pause
    exit /b 1
)

:: 检查监控脚本是否存在
if not exist "monitor-website.js" (
    echo [错误] 未找到监控脚本 monitor-website.js
    pause
    exit /b 1
)

:: 创建日志目录
if not exist "logs" mkdir logs

echo [信息] 启动网站监控服务...
echo [信息] 监控地址: http://localhost:3000
echo [信息] 检查间隔: 5分钟
echo [信息] 日志文件: logs\website-monitor.log
echo.

:: 启动监控服务
node monitor-website.js

if %errorlevel% neq 0 (
    echo [错误] 监控服务启动失败，错误代码: %errorlevel%
    pause
    exit /b %errorlevel%
)

echo [信息] 监控服务已正常退出
pause
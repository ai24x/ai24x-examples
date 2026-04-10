@echo off
chcp 65001 >nul
title AI24X网站快速监控
echo ========================================
echo      AI24X网站快速监控启动
echo ========================================
echo 时间: %date% %time%
echo.

:: 检查网站状态
echo [检查] 网站运行状态...
curl -s -o nul -w "状态码: %%{http_code}\n" http://localhost:3000

echo.
echo [信息] 启动监控服务...
echo [信息] 按Ctrl+C停止监控
echo.

:: 启动监控
node monitor-website.js
@echo off
chcp 65001 >nul
echo ========================================
echo AI24X网站服务 - 自动启动和监控
echo ========================================
echo.

REM 创建Windows计划任务自动启动
echo 📅 正在配置自动启动服务...
echo.

REM 检查是否以管理员身份运行
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  需要管理员权限来创建计划任务
    echo 请右键点击此脚本，选择"以管理员身份运行"
    pause
    exit /b 1
)

REM 获取当前目录
set "CURRENT_DIR=%~dp0"
set "SCRIPT_PATH=%CURRENT_DIR%start-server.bat"

REM 创建计划任务（用户登录时启动）
echo 🔧 创建计划任务：AI24X-Website-AutoStart
schtasks /create /tn "AI24X-Website-AutoStart" ^
    /tr "%SCRIPT_PATH%" ^
    /sc onlogon ^
    /rl highest ^
    /f

if %errorlevel% equ 0 (
    echo ✅ 计划任务创建成功！
    echo 📋 任务名称：AI24X-Website-AutoStart
    echo ⏰ 触发条件：用户登录时自动启动
    echo 📍 执行脚本：%SCRIPT_PATH%
) else (
    echo ❌ 计划任务创建失败
)

echo.
echo 🔄 立即启动服务器...
echo.

REM 启动服务器
cd /d "%CURRENT_DIR%"
call start-server.bat
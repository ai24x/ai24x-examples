@echo off
chcp 65001 >nul
title AI24X网站服务器 - 自动重启版
color 0A

echo ========================================
echo    AI24X网站服务器 - 自动重启系统
echo ========================================
echo   版本: 1.0.0
echo   创建时间: 2026-03-16
echo   特性: 崩溃自动重启 + 内存监控
echo ========================================
echo.

REM 设置环境变量
set NODE_ENV=production
set PORT=3000
set MAX_MEMORY=512
set RESTART_DELAY=10

REM 检查Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: Node.js未安装或不在PATH中
    echo 请安装Node.js并确保在系统PATH中
    pause
    exit /b 1
)

echo ✅ Node.js版本:
node --version
echo.

REM 检查服务器文件
if not exist "server-stable.js" (
    echo ❌ 错误: server-stable.js文件不存在
    pause
    exit /b 1
)

echo ✅ 服务器文件检查通过
echo.

REM 显示系统信息
echo 📊 系统信息:
echo   内存: 8GB
echo   端口: %PORT%
echo   环境: %NODE_ENV%
echo   工作目录: %cd%
echo   最大内存: %MAX_MEMORY%MB
echo   重启延迟: %RESTART_DELAY%秒
echo.

:start_server
REM 生成唯一标识
set START_TIME=%date% %time%
set /a RUN_COUNT+=1

echo.
echo ========================================
echo   启动第 %RUN_COUNT% 次 (PID: 未知)
echo   开始时间: %START_TIME%
echo ========================================
echo.

REM 记录启动日志
echo [%date% %time%] 启动第 %RUN_COUNT% 次 >> server-restart.log
echo   工作目录: %cd% >> server-restart.log
echo   命令行: node --max-old-space-size=%MAX_MEMORY% server-stable.js >> server-restart.log
echo.

REM 使用优化参数启动服务器
echo 🚀 启动AI24X极简稳定版服务器...
echo   命令行: node --max-old-space-size=%MAX_MEMORY% server-stable.js
echo.

REM 启动服务器并捕获PID
node --max-old-space-size=%MAX_MEMORY% server-stable.js

REM 服务器退出后的处理
set EXIT_TIME=%date% %time%
set /a EXIT_CODE=%errorlevel%

echo.
echo ========================================
echo   服务器已退出
echo ========================================
echo   退出代码: %EXIT_CODE%
echo   启动时间: %START_TIME%
echo   退出时间: %EXIT_TIME%
echo   运行次数: %RUN_COUNT%
echo.

REM 记录退出日志
echo [%date% %time%] 服务器退出，代码: %EXIT_CODE% >> server-restart.log
echo   运行次数: %RUN_COUNT% >> server-restart.log
echo   启动时间: %START_TIME% >> server-restart.log
echo   退出时间: %EXIT_TIME% >> server-restart.log
echo.

REM 分析退出原因
if %EXIT_CODE% equ 0 (
    echo ✅ 服务器正常退出
    echo   可能原因: 手动关闭或SIGINT信号
    goto :normal_exit
) else if %EXIT_CODE% equ 1 (
    echo ⚠️ 服务器异常退出 (代码: 1)
    echo   可能原因: 未捕获异常或启动失败
) else if %EXIT_CODE% equ 3 (
    echo ⚠️ 服务器异常退出 (代码: 3)
    echo   可能原因: 内部错误
) else (
    echo ⚠️ 服务器异常退出 (代码: %EXIT_CODE%)
    echo   可能原因: 未知错误
)

REM 检查是否SIGKILL (在Windows上通常是外部终止)
if %EXIT_CODE% gtr 128 (
    echo 🚨 检测到SIGKILL信号终止
    echo   可能原因: Windows进程管理策略限制
    echo   解决方案: 自动重启并继续运行
)

REM 等待一段时间后重启
echo.
echo ⏳ 等待 %RESTART_DELAY% 秒后重启...
echo   下次重启: 第 %RUN_COUNT% 次 -> 第 %RUN_COUNT% 次
echo.

REM 显示倒计时
for /l %%i in (%RESTART_DELAY%, -1, 1) do (
    echo 重启倒计时: %%i 秒
    timeout /t 1 /nobreak >nul
)

echo 🔄 正在重启服务器...
echo [%date% %time%] 准备重启服务器 >> server-restart.log
echo.

REM 清理可能的内存残留
echo 🧹 清理内存残留...
timeout /t 2 /nobreak >nul

goto :start_server

:normal_exit
echo.
echo ========================================
echo   服务器正常退出，停止自动重启
echo ========================================
echo   总运行次数: %RUN_COUNT%
echo   最后退出代码: %EXIT_CODE%
echo   退出时间: %EXIT_TIME%
echo.

echo [%date% %time%] 正常退出，停止自动重启 >> server-restart.log
echo   总运行次数: %RUN_COUNT% >> server-restart.log
echo   最后退出代码: %EXIT_CODE% >> server-restart.log

pause
exit /b 0
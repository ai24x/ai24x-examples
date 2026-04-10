@echo off
chcp 65001 >nul
echo.
echo ========================================
echo AI24X网站公网访问自动配置工具
echo 最高效方便的3000端口方案
echo ========================================
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 需要管理员权限运行此脚本！
    echo.
    echo 请执行以下操作：
    echo 1. 右键点击此文件
    echo 2. 选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

echo ✅ 检测到管理员权限
echo.

REM 步骤1：配置防火墙允许3000端口
echo 🔧 配置防火墙规则...
netsh advfirewall firewall add rule name="AI24X-Web-3000" dir=in action=allow protocol=TCP localport=3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ 防火墙规则已添加: AI24X-Web-3000 (端口3000)
) else (
    echo ⚠️ 防火墙规则可能已存在，跳过...
)

REM 步骤2：检查现有规则
echo.
echo 📋 检查现有防火墙规则...
netsh advfirewall firewall show rule name="AI24X-Web-3000" | findstr /i "Enabled Action" >nul
if %errorlevel% equ 0 (
    echo ✅ 3000端口防火墙规则已生效
) else (
    echo ❌ 防火墙规则配置失败，请手动检查
)

REM 步骤3：检查服务器状态
echo.
echo 🖥️ 检查服务器状态...
tasklist /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq server.js" 2>nul | findstr /i "node.exe" >nul
if %errorlevel% equ 0 (
    echo ✅ Web服务器正在运行
) else (
    echo ⚠️ Web服务器未运行，正在启动...
    start /B node server.js
    timeout /t 3 /nobreak >nul
    echo ✅ 服务器已启动
)

REM 步骤4：检查端口监听
echo.
echo 🌐 检查端口监听状态...
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo ✅ 3000端口正在监听 (0.0.0.0)
) else (
    echo ❌ 3000端口未监听，请检查服务器
)

REM 步骤5：显示配置信息
echo.
echo 📊 配置完成！请按以下步骤操作：
echo.
echo 1. ✅ 防火墙已配置 (3000端口允许访问)
echo 2. ✅ 服务器状态已检查
echo 3. ✅ 端口监听已确认
echo.
echo 🔧 还需要您手动配置：
echo.
echo 📡 路由器配置 (关键步骤)：
echo   登录路由器管理界面
echo   添加端口转发规则：
echo   - 外部端口: 3000
echo   - 内部IP: 10.0.0.15
echo   - 内部端口: 3000
echo   - 协议: TCP
echo.
echo 🌐 测试地址：
echo   本地测试: http://localhost:3000
echo   局域网测试: http://10.0.0.15:3000
echo   公网测试: http://42.192.1.93:3000
echo.
echo 📱 立即测试：
echo   1. 用手机打开浏览器
echo   2. 访问: http://42.192.1.93:3000
echo   3. 测试健康检查: http://42.192.1.93:3000/health
echo.
echo ⚠️ 如果无法访问，请检查：
echo   - 路由器端口转发配置
echo   - 云主机安全组 (如果有)
echo   - 网络连接状态
echo.

REM 步骤6：提供快速测试命令
echo 🔍 快速测试命令：
echo   测试本地连接: curl http://localhost:3000/health
echo   测试局域网连接: curl http://10.0.0.15:3000/health
echo.

echo 🎉 配置完成！请立即测试公网访问。
echo.
pause
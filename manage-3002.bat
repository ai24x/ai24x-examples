@echo off
echo ========================================
echo AI24X网站管理脚本 (端口3002) - ai24x02
echo ========================================
echo.

cd /d "%~dp0"

:menu
echo.
echo 请选择操作:
echo 1. 查看网站状态
echo 2. 查看网站日志
echo 3. 重启网站
echo 4. 停止网站
echo 5. 启动网站
echo 6. 测试网站访问
echo 7. 检查端口占用
echo 8. 退出
echo.

set /p choice="请输入选项 (1-8): "

if "%choice%"=="1" goto status
if "%choice%"=="2" goto logs
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto start
if "%choice%"=="6" goto test
if "%choice%"=="7" goto port
if "%choice%"=="8" goto exit

echo 无效选项，请重新输入！
goto menu

:status
echo.
echo === 网站状态 ===
pm2 status ai24x02
goto menu

:logs
echo.
echo === 网站日志 (按Ctrl+C退出) ===
pm2 logs ai24x02
goto menu

:restart
echo.
echo === 重启网站 ===
pm2 restart ai24x02
echo 网站已重启！
goto menu

:stop
echo.
echo === 停止网站 ===
pm2 stop ai24x02
echo 网站已停止！
goto menu

:start
echo.
echo === 启动网站 ===
pm2 start ai24x02
if errorlevel 1 (
    echo 启动失败，尝试重新创建...
    pm2 delete ai24x02
    pm2 start server-3002.js --name "ai24x02" --watch
)
echo 网站已启动！
goto menu

:test
echo.
echo === 测试网站访问 ===
echo 测试首页访问...
curl -I http://localhost:3002
echo.
echo 测试健康检查...
curl http://localhost:3002/health
echo.
goto menu

:port
echo.
echo === 检查端口占用 ===
netstat -ano | findstr :3002
echo.
goto menu

:exit
echo.
echo 退出管理脚本。
pause
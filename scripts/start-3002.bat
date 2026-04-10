@echo off
echo ========================================
echo AI24X网站启动脚本 (端口3002) - ai24x02
echo ========================================
echo.

cd /d "%~dp0"

echo 1. 检查PM2是否已安装...
pm2 --version >nul 2>&1
if errorlevel 1 (
    echo PM2未安装，正在安装...
    npm install -g pm2
    if errorlevel 1 (
        echo PM2安装失败！
        pause
        exit /b 1
    )
    echo PM2安装成功！
) else (
    echo PM2已安装。
)

echo.
echo 2. 检查网站是否已在运行...
pm2 describe ai24x02 >nul 2>&1
if errorlevel 1 (
    echo 网站未运行，正在启动...
) else (
    echo 网站已在运行，正在重启...
    pm2 stop ai24x02
    pm2 delete ai24x02
)

echo.
echo 3. 安装依赖...
npm install
if errorlevel 1 (
    echo 依赖安装失败！
    pause
    exit /b 1
)
echo 依赖安装成功！

echo.
echo 4. 启动网站...
pm2 start server-3002.js --name "ai24x02" --watch

echo.
echo 5. 保存PM2配置...
pm2 save

echo.
echo 6. 设置PM2开机自启...
pm2 startup
echo 请按照上面的提示执行命令以启用开机自启

echo.
echo ========================================
echo 网站启动完成！
echo.
echo 访问地址: http://localhost:3002
echo 健康检查: http://localhost:3002/health
echo 性能报告: http://localhost:3002/performance-report
echo.
echo PM2管理命令:
echo   pm2 status              - 查看状态
echo   pm2 logs ai24x02        - 查看日志
echo   pm2 stop ai24x02        - 停止网站
echo   pm2 restart ai24x02     - 重启网站
echo   pm2 delete ai24x02      - 删除进程
echo ========================================
echo.

pause
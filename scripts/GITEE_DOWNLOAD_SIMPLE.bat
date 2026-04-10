@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    AI24X网站 - Gitee下载部署脚本
echo ========================================
echo.

REM 检查Git是否安装
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Git未安装，请先安装Git
    echo 安装方法: choco install git -y
    echo 或者访问: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo ✅ Git已安装
git --version

echo.
echo 📋 开始从Gitee下载AI24X网站...
echo.

REM 目标目录
set TARGET_DIR=C:\副脑03\ai24x-website
set GITEE_REPO=https://gitee.com/ai24x/ai24x-website.git

echo 目标目录: %TARGET_DIR%
echo Gitee仓库: %GITEE_REPO%
echo.

REM 检查目标目录
if exist "%TARGET_DIR%" (
    echo 📁 目标目录已存在，检查是否为Git仓库...
    
    cd /d "%TARGET_DIR%"
    if exist ".git" (
        echo ✅ 是Git仓库，执行拉取更新...
        git pull origin master
    ) else (
        echo ⚠️ 不是Git仓库，备份后重新克隆...
        
        set BACKUP_DIR=%TARGET_DIR%.backup.%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%
        echo 备份到: %BACKUP_DIR%
        move "%TARGET_DIR%" "%BACKUP_DIR%"
        
        cd /d "C:\"
        git clone %GITEE_REPO% "%TARGET_DIR%"
    )
) else (
    echo 📁 目标目录不存在，直接克隆仓库...
    cd /d "C:\"
    git clone %GITEE_REPO% "%TARGET_DIR%"
)

echo.
echo ✅ Gitee下载完成！
echo.

REM 验证关键文件
echo 🔍 验证关键文件...
echo.

cd /d "%TARGET_DIR%"

if exist "server-clean-fixed.js" (
    for %%F in ("server-clean-fixed.js") do set SIZE=%%~zF
    echo ✅ server-clean-fixed.js - 存在 (%SIZE% 字节)
) else (
    echo ❌ server-clean-fixed.js - 不存在
)

if exist "index.html" (
    echo ✅ index.html - 存在
) else (
    echo ❌ index.html - 不存在
)

if exist "tools-index.html" (
    echo ✅ tools-index.html - 存在
) else (
    echo ❌ tools-index.html - 不存在
)

if exist "login.html" (
    echo ✅ login.html - 存在
) else (
    echo ❌ login.html - 不存在
)

if exist "signup.html" (
    echo ✅ signup.html - 存在
) else (
    echo ❌ signup.html - 不存在
)

if exist "data\fission-rewards.json" (
    echo ✅ data\fission-rewards.json - 存在
) else (
    echo ❌ data\fission-rewards.json - 不存在
)

if exist "api\fission-db.js" (
    echo ✅ api\fission-db.js - 存在
) else (
    echo ❌ api\fission-db.js - 不存在
)

if exist "share-system\dashboard.html" (
    echo ✅ share-system\dashboard.html - 存在
) else (
    echo ❌ share-system\dashboard.html - 不存在
)

echo.
echo 🎯 副脑03现在可以启动网站服务：
echo 1. 启动服务: node server-clean-fixed.js
echo 2. 访问后台: http://localhost:3000/share-system/dashboard.html
echo 3. 测试页面: 首页、工具页、登录页、注册页
echo 4. 验证API: 数据库API接口
echo.

echo 📊 Git仓库状态：
git status --short
echo.
git log --oneline -3
echo.

echo 🎉 Gitee下载完成！副脑03部署就绪！
echo.
pause
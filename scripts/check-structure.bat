@echo off
echo 🔍 检查AI24X Token平台目录结构...
echo ========================================

set REQUIRED_DIRS=api web db config scripts docs
set MISSING_COUNT=0

echo 检查必需目录...
for %%d in (%REQUIRED_DIRS%) do (
    if not exist "%%d\" (
        echo ❌ 缺少目录: %%d
        set /a MISSING_COUNT+=1
    ) else (
        echo ✅ 目录存在: %%d
    )
)

echo.
echo 检查非法顶层目录...
set ILLEGAL_COUNT=0
for /d %%d in (*) do (
    set FOUND=0
    for %%r in (%REQUIRED_DIRS%) do (
        if "%%d"=="%%r" set FOUND=1
    )
    if "!FOUND!"=="0" (
        echo ⚠️  发现非法目录: %%d
        set /a ILLEGAL_COUNT+=1
    )
)

echo.
echo 检查git状态...
git status --porcelain >nul 2>&1
if errorlevel 1 (
    echo ✅ 没有未提交的更改
) else (
    echo ⚠️  有未提交的更改
    echo    请执行: git add . ^&^& git commit -m "更新" ^&^& git push
)

echo.
echo ========================================
echo 📋 检查完成

if %MISSING_COUNT% equ 0 (
    echo ✅ 所有必需目录都存在
) else (
    echo ❌ 缺少 %MISSING_COUNT% 个目录
    echo    请执行: mkdir api web db config scripts docs
)

if %ILLEGAL_COUNT% equ 0 (
    echo ✅ 没有非法顶层目录
) else (
    echo ⚠️  发现 %ILLEGAL_COUNT% 个非法目录
    echo    请将文件移动到标准目录中
)

echo.
echo 💡 标准目录结构:
echo    api/     后端接口
echo    web/     前端页面
echo    db/      数据库
echo    config/  配置
echo    scripts/ 脚本
echo    docs/    文档

echo.
pause
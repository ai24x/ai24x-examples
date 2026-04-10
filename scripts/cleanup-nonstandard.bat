@echo off
echo 🧹 清理非标准目录结构...
echo ========================================

set STANDARD_DIRS=api web db config scripts docs
set KEEP_FILES=README.md .gitignore

echo 保留标准目录: %STANDARD_DIRS%
echo 保留文件: %KEEP_FILES%

echo.
echo 检查需要清理的目录...
for /d %%d in (*) do (
    set FOUND=0
    for %%s in (%STANDARD_DIRS%) do (
        if "%%d"=="%%s" set FOUND=1
    )
    if "!FOUND!"=="0" (
        echo ❌ 非标准目录: %%d
        echo    建议移动到对应标准目录
    )
)

echo.
echo 检查需要清理的文件...
for %%f in (*) do (
    set FOUND=0
    for %%k in (%KEEP_FILES%) do (
        if "%%f"=="%%k" set FOUND=1
    )
    if "!FOUND!"=="0" (
        if not "%%f"=="cleanup-nonstandard.bat" (
            echo ⚠️  非标准顶层文件: %%f
            echo    建议移动到对应标准目录
        )
    )
)

echo.
echo 💡 建议操作:
echo 1. 将前端文件移动到 web/ 目录
echo 2. 将后端文件移动到 api/ 目录
echo 3. 将数据库文件移动到 db/ 目录
echo 4. 将配置文件移动到 config/ 目录
echo 5. 将脚本文件移动到 scripts/ 目录
echo 6. 将文档文件移动到 docs/ 目录

echo.
echo 🚨 注意: 不要删除重要的网站文件！
echo    原有网站功能需要保留，只需重新组织目录结构

echo.
pause
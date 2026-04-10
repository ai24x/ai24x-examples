@echo off
echo 🚀 解决HTML文件创建卡死问题
echo.

echo 📊 检查内存...
wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value

echo.
echo 🧹 清理临时文件...
del /q /f "%TEMP%\*" 2>nul
del /q /f "%TMP%\*" 2>nul
echo    临时文件已清理

echo.
echo 🛠️ 创建HTML快速生成工具...
(
echo @echo off
echo setlocal enabledelayedexpansion
echo.
echo if "%%1"=="" (
echo     echo 使用方法: %%~n0 ^<文件名^> ^<标题^> ^<内容^>
echo     echo 示例: %%~n0 mypage.html "我的页面" "这是内容"
echo     exit /b 1
echo )
echo.
echo set "file=%%~1"
echo set "title=%%~2"
echo if "!title!"=="" set "title=新页面"
echo.
echo set "content=%%~3"
echo if "!content!"=="" set "content=快速生成的HTML页面"
echo.
echo (
echo ^<!DOCTYPE html^>
echo ^<html^>
echo ^<head^>
echo     ^<meta charset="UTF-8"^>
echo     ^<title^>!title!^</title^>
echo     ^<style^>
echo         body { font-family: Arial; padding: 20px; }
echo         h1 { color: #2c3e50; }
echo     ^</style^>
echo ^</head^>
echo ^<body^>
echo     ^<h1^>!title!^</h1^>
echo     ^<p^>!content!^</p^>
echo     ^<p^>生成时间: %date% %time%^</p^>
echo ^</body^>
echo ^</html^>
echo ) ^> "!file!"
echo.
echo echo ✅ 已创建: !file!
) > "%USERPROFILE%\Desktop\create-html.bat"

echo    工具已创建到桌面: create-html.bat

echo.
echo 🧪 创建测试文件...
(
echo ^<!DOCTYPE html^>
echo ^<html^>
echo ^<head^>
echo     ^<title^>测试页面^</title^>
echo     ^<style^>
echo         body { font-family: Arial; padding: 30px; }
echo         .success { color: green; font-size: 24px; }
echo     ^</style^>
echo ^</head^>
echo ^<body^>
echo     ^<h1 class="success"^>✅ HTML文件创建测试^</h1^>
echo     ^<p^>如果这个页面能正常打开，说明HTML创建功能正常。^</p^>
echo     ^<p^>生成时间: %date% %time%^</p^>
echo ^</body^>
echo ^</html^>
) > test-ok.html

echo    测试文件已创建: test-ok.html

echo.
echo 💡 优化建议:
echo 1. 使用批处理文件创建HTML（最快）
echo 2. 禁用编辑器的自动格式化功能
echo 3. 使用Notepad++代替复杂编辑器
echo 4. 先创建小文件，再逐步添加内容
echo 5. 避免在浏览器中直接编辑HTML

echo.
echo 🎉 优化完成！
echo 📁 工具位置: %USERPROFILE%\Desktop\create-html.bat
echo 💡 使用方法: create-html.bat mypage.html "我的页面" "这是内容"
echo.

pause
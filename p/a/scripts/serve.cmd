@echo off
setlocal

rem NOTE: keep this file ASCII-friendly for cmd.exe parsing.

cd /d "%~dp0..\web" || (
  echo Failed to cd to web directory.
  echo Expected: "%~dp0..\web"
  pause
  exit /b 1
)

echo.
echo Local static server:
echo   http://127.0.0.1:18001/index.html
echo.
echo Serving directory: %cd%
echo Press Ctrl+C to stop the server.
echo.

start "" "http://127.0.0.1:18001/index.html"

rem If port is occupied, kill the existing listener first.
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":18001" ^| findstr LISTENING') do (
  echo Killing existing listener PID %%P on :18001 ...
  taskkill /PID %%P /F >nul 2>nul
)

py -3 -m http.server 18001
if errorlevel 1 python -m http.server 18001
if errorlevel 1 (
  echo.
  echo Python not found. Please install Python.
  pause
)

endlocal

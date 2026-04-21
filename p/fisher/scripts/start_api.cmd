@echo off
chcp 65001 >nul
pushd "%~dp0..\api\server" || (
  echo Failed to cd to p\fisher\api\server
  pause
  exit /b 1
)

echo.
echo 山海渔 Fisher API  本地开发
echo   Docs:   http://127.0.0.1:18041/docs
echo   Health: http://127.0.0.1:18041/health
echo.

py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 18041 --reload
if errorlevel 1 python -m uvicorn app.main:app --host 127.0.0.1 --port 18041 --reload
if errorlevel 1 (
  echo.
  echo Failed. Install deps: pip install -r requirements.txt
  pause
)

popd

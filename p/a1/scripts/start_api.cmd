@echo off
chcp 65001 >nul
pushd "%~dp0..\\api\\server" || (
  echo Failed to cd to p\a\api\server directory.
  echo Expected: %~dp0..\\api\\server
  pause
  exit /b 1
)

echo.
echo AI24X a.ai24x.com API (local dev)
echo   Docs:        http://127.0.0.1:18033/docs
echo   Root 引导:   http://127.0.0.1:18033/   (JSON 内含 admin_login 等路径)
echo   管理台登录:  见 .env 中 AI24X_ADMIN_MOUNT_PATH，默认 /admin20260501/login
echo.
echo Tip: activate venv first if you have one:
echo   .\.venv\Scripts\Activate.ps1
echo.

py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 18033 --reload
if errorlevel 1 python -m uvicorn app.main:app --host 127.0.0.1 --port 18033 --reload
if errorlevel 1 (
  echo.
  echo Failed to start uvicorn. Ensure dependencies installed:
  echo   pip install -r requirements.txt
  echo.
  pause
)

popd


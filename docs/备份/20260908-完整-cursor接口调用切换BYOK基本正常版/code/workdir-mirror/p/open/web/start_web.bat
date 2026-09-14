@echo off

cd /d "%~dp0.."

cd api

echo.

echo Site + API on port 8000 (same process)

echo   http://localhost:8000/

echo   http://localhost:8000/en/index.html

echo   http://localhost:8000/docs

echo.

python main.py



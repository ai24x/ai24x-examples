@echo off
REM 中台 core API 启动（PM2 注册：core-api-18043）
cd /d %~dp0
python -m uvicorn app.main:app --host 127.0.0.1 --port 18043

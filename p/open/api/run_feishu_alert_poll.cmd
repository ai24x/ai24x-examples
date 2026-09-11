@echo off
REM AI24X Feishu alert digest / poll — run from Scheduled Task (Start in = this folder's parent api)
cd /d "%~dp0"
set OPS_ALERT_API=http://127.0.0.1:8002
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts_feishu_alert_poll.py %*
) else (
  python scripts_feishu_alert_poll.py %*
)

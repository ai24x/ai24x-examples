@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting AI Hang Qing Guan - Daily Report Service (port 18013) ...
python server.py
pause

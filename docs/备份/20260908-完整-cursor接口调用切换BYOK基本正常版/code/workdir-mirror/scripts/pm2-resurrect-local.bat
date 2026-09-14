@echo off
setlocal
chcp 65001 >nul

REM Repo root = parent of scripts\
cd /d "%~dp0.."
if not exist "ecosystem.local.config.js" (
  echo [pm2-resurrect-local] ERROR: ecosystem.local.config.js not found. Is this the repo root parent?
  exit /b 1
)

where pm2 >nul 2>&1
if errorlevel 1 (
  echo [pm2-resurrect-local] ERROR: pm2 not in PATH. Install: npm i -g pm2
  exit /b 1
)

echo [pm2-resurrect-local] cwd=%CD%
pm2 resurrect
exit /b %ERRORLEVEL%

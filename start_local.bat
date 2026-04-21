@echo off

cd /d "%~dp0"

echo Starting AI24X via PM2...
echo - core-8000    : http://localhost:8000/
echo - a-web-18001  : http://localhost:18001/
echo - a-api-18031  : http://localhost:18031/
echo.

rem Use PM2 to manage all local services (Windows-friendly config).
rem Default: allow running without local PostgreSQL.
pm2 start ecosystem.local.config.js

rem Persist current process list for auto-resurrect (optional but recommended).
pm2 save

echo.

echo Home:  http://localhost:8000/index.html  (or http://localhost:8000/)

echo EN:    http://localhost:8000/en/index.html

echo API:   http://localhost:8000/docs

echo.
echo Tips:
echo   pm2 status
echo   pm2 logs core-8000
echo   pm2 restart core-8000
echo   pm2 stop core-8000 a-web-18001 a-api-18031
echo.

echo.



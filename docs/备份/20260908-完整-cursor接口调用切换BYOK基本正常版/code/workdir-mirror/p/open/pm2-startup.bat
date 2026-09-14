@echo off
REM AI24X PM2 auto-startup script — runs at Windows boot
cd /d "E:\AI24X\ai24x-website\ai24x01"
call pm2 resurrect

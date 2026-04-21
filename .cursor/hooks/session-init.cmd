@echo off
setlocal enabledelayedexpansion

REM Project hook: sessionStart (fire-and-forget)
REM Reads stdin JSON but does not depend on it.

python ".cursor/hooks/session_init.py" < CON >NUL 2>&1
exit /b 0


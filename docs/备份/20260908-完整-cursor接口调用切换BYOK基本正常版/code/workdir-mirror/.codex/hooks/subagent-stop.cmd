@echo off
setlocal enabledelayedexpansion

REM Project hook: subagentStop
REM Appends a brief note into today's memory/daily file.

python ".cursor/hooks/subagent_stop.py"
exit /b 0


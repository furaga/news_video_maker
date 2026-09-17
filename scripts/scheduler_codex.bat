@echo off
setlocal
cd /d "%~dp0.." || exit /b 1
if not exist logs mkdir logs
if not exist logs exit /b 1
set "PYTHONIOENCODING=utf-8"
echo [INFO] scheduler_codex.bat start
echo [INFO] Current directory: %cd%
echo [INFO] Running Codex scheduler. Log: logs\scheduler_codex.log
call uv run python scripts/scheduler.py --once --engine codex %* >> logs\scheduler_codex.log 2>&1
set "RESULT=%ERRORLEVEL%"
echo [INFO] scheduler_codex.bat finished, exit code: %RESULT%
exit /b %RESULT%

@echo off
cd /d %~dp0..
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
echo [INFO] scheduler.bat start
echo [INFO] Current directory: %cd%
echo [INFO] Running: uv run python scripts/scheduler.py --once
uv run python scripts/scheduler.py --once >> logs\scheduler.log 2>&1
echo [INFO] scheduler.bat finished
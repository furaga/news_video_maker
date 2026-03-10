@echo off
cd /d %~dp0..
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
uv run python scripts/run_pipeline.py >> logs\scheduler.log 2>&1

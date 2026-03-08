@echo off
cd /d %~dp0..
if not exist logs mkdir logs
uv run python scripts/run_pipeline.py >> logs\scheduler.log 2>&1

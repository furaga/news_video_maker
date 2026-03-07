@echo off
cd /d %~dp0..
uv run python scripts/run_pipeline.py >> logs\scheduler.log 2>&1

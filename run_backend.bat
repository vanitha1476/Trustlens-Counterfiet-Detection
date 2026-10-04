@echo off
echo ========================================================
echo Starting TrustLens Backend on http://localhost:8000
echo ========================================================
set PYTHONPATH=%cd%
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
pause

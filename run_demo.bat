@echo off
REM IR_03 Source-Aware Misinformation Detection - Phase-I review demo launcher (offline).
REM Double-click, or run from any terminal. Opens http://localhost:8501 in your browser.
cd /d "%~dp0"
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set PYTHONIOENCODING=utf-8
echo Starting demo... first start takes 1-2 minutes (loading models and frozen rankings).
echo If the browser does not open, go to http://localhost:8501
python -m streamlit run experiments\esa_nov2026\demo_app.py --browser.gatherUsageStats false --server.port 8501
if errorlevel 1 (
  echo.
  echo The demo did not start. Fallback: open results\esa_nov2026\demo\fallback\INDEX.html
  pause
)

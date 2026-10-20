@echo off
cd /d "%~dp0"
rem Optional: set GBB_DATA_DIR to the folder of real GBB Excel exports before running, e.g.
rem   set "GBB_DATA_DIR=C:\Users\you\BI Report Dataset\GBB"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false
) else (
  python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false
)

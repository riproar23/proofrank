@echo off
title ProofRank Demo
cd /d "%~dp0"

echo.
echo  Starting ProofRank demo...
echo  Opening at http://localhost:8501
echo.

:: try venv python first, fall back to system python
if exist ".venv\Scripts\python.exe" (
    start "" http://localhost:8501
    .venv\Scripts\python.exe -m streamlit run app.py --server.headless true
) else (
    start "" http://localhost:8501
    python -m streamlit run app.py --server.headless true
)

pause

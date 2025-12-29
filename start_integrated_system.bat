@echo off
echo Starting AI GURU Platform...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not installed
    pause
    exit /b 1
)

REM Install dependencies if needed
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing Streamlit...
    pip install streamlit
)

echo.
echo Starting system...
echo.
echo AI GURU Platform is starting!
echo Access: http://localhost:8501
echo.

streamlit run main.py --logger.level=warning
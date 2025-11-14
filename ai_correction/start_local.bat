@echo off
REM AI批改系统 - 本地启动脚本
echo ========================================
echo AI批改系统 - 本地环境启动
echo ========================================
echo.

REM 激活虚拟环境（如果存在）
if exist venv\Scripts\activate.bat (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
)

REM 设置环境变量
set ENVIRONMENT=development
set DATABASE_URL=sqlite:///ai_correction.db

echo 检查本地环境...
python local_runner.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo 环境检查通过！
    echo ========================================
    echo.
    echo 启动Streamlit应用...
    streamlit run main.py
) else (
    echo.
    echo ========================================
    echo 环境检查失败！请查看错误信息
    echo ========================================
    pause
)

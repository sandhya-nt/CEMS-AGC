@echo off
REM CEMS Desktop Launcher - Windows Batch Script
REM Double-click this file to launch CEMS

cd /d "%~dp0"

echo.
echo ========================================================
echo   CEMS - Campus Event Management System
echo   Amritsar Group of Colleges
echo ========================================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then run: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment and launch CEMS
call .venv\Scripts\activate.bat
python launch_cems.py

pause

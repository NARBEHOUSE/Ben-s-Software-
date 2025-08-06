@echo off
REM © 2025 NARBE House – Licensed under CC BY-NC 4.0
REM Windows batch launcher for Ben's Accessibility Software

echo 🚀 Ben's Accessibility Software - Windows Launcher
echo ==================================================
echo.

REM Check if UV is installed
uv --version >nul 2>&1
if errorlevel 1 (
    echo ❌ UV is not installed or not in PATH
    echo 💡 Please install UV first: https://docs.astral.sh/uv/
    echo.
    echo On Windows, run:
    echo   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv" (
    echo 🔧 Setting up virtual environment...
    uv sync
    if errorlevel 1 (
        echo ❌ Failed to set up environment
        pause
        exit /b 1
    )
)

REM Run the Python launcher
echo 🐍 Starting Python launcher...
uv run run.py

pause

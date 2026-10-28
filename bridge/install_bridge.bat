@echo off
chcp 65001 >nul
title HaloBridge Setup
cd /d "%~dp0"

echo Creating a virtual environment ...
python -m venv venv
if errorlevel 1 (
  echo.
  echo Python was not found. Install Python 3.9+ and tick "Add Python to PATH".
  pause
  exit /b 1
)

echo Installing hidapi ...
"%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
"%~dp0venv\Scripts\python.exe" -m pip install hidapi -i https://mirrors.aliyun.com/pypi/simple/
if errorlevel 1 (
  echo.
  echo hidapi install failed. Try another index: -i https://pypi.org/simple
  pause
  exit /b 1
)

echo.
echo Done. Run start_bridge.bat to test, or use the watchdog for daily use.
pause

@echo off
chcp 65001 >nul
title HaloBridge
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0halo_bridge.py"
pause

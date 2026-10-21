@echo off
cd /d "%~dp0"
python open_map.py %*
if errorlevel 1 (
    echo.
    pause
)

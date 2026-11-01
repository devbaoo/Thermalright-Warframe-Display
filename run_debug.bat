@echo off
title Thermalright Warframe Display - Debug Console
cd /d "%~dp0"
echo ========================================================
echo   Thermalright Frozen Warframe 360 SE - Debug Console
echo ========================================================
echo Starting app...
python main.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo App exited with code %ERRORLEVEL%.
    echo Check app.log for details.
    pause
)


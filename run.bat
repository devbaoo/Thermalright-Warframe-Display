@echo off
cd /d "%~dp0"
if exist "ThermalrightWarframe.exe" (
    start "" "ThermalrightWarframe.exe" %*
) else (
    start "" pythonw.exe main.py %*
)

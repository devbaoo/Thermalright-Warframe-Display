@echo off
cd /d "%~dp0"
if exist "C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe" (
    start "" "C:\Users\Admin\AppData\Local\Programs\Python\Python312\pythonw.exe" main.py %*
) else (
    start "" pythonw.exe main.py %*
)

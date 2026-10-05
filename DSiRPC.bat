@echo off
rem Starts DSiRPC in the tray, by the clock. Right-click its icon for the menu.
rem Run Setup.bat once first.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo DSiRPC isn't set up yet: run Setup.bat first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" dsirpc.py tray

@echo off
rem Starts DSiRPC in the tray, by the clock. Right-click its icon for the menu.
rem Run Setup.bat once first.
cd /d "%~dp0"
set "PYW="
if exist "python\pythonw.exe" set "PYW=python\pythonw.exe"
if not defined PYW if exist ".venv\Scripts\pythonw.exe" set "PYW=.venv\Scripts\pythonw.exe"
if not defined PYW (
    echo DSiRPC isn't set up yet: run Setup.bat first.
    pause
    exit /b 1
)
start "" "%PYW%" dsirpc.py tray

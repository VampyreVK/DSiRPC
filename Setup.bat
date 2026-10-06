@echo off
rem DSiRPC setup: asks a few questions (python dsirpc.py setup). Safe to run
rem again any time, for example to sign in to RetroAchievements or add a
rem game's achievement set.
rem
rem A release download comes with its own Python (the python folder). A copy
rem of the source code gets one first, in the .venv folder, with the packages
rem DSiRPC needs.
setlocal
cd /d "%~dp0"
title DSiRPC setup

if exist "python\python.exe" goto bundled

echo.
echo   DSiRPC setup
echo   ============
echo   First, DSiRPC gets its own copy of Python and the packages it needs, in
echo   the .venv folder here. That takes a minute the first time; after that
echo   it's quick.
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "pass" 2>nul
    if errorlevel 1 (
        echo   DSiRPC's Python was set up in a different folder, so it's being set up again...
        call :makevenv
        if errorlevel 1 goto nopython
    )
) else (
    echo   Setting up DSiRPC's own Python...
    call :makevenv
    if errorlevel 1 goto nopython
)

echo   Installing the packages DSiRPC needs: pypresence, pygame-ce, Pillow, pystray...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo   The packages couldn't be installed. The messages above say why; most
    echo   often it's no internet connection. Fix that and run Setup.bat again.
    pause
    exit /b 1
)
echo   Done.

".venv\Scripts\python.exe" dsirpc.py setup
exit /b %errorlevel%

:bundled
"python\python.exe" dsirpc.py setup
exit /b %errorlevel%

:makevenv
py -3 -m venv .venv 2>nul
if not errorlevel 1 exit /b 0
python -m venv .venv
exit /b %errorlevel%

:nopython
echo.
echo   DSiRPC needs Python 3, and it doesn't seem to be installed.
echo   1. Get it from https://www.python.org/downloads/
echo   2. In its installer, tick "Add python.exe to PATH" before installing.
echo   3. Run Setup.bat again.
echo   Or download DSiRPC from the Releases page instead, which comes with Python.
pause
exit /b 1

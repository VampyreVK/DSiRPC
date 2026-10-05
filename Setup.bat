@echo off
rem DSiRPC setup: makes the Python environment in .venv, installs the packages
rem DSiRPC needs, then asks a few questions (python dsirpc.py setup).
rem Safe to run again any time, for example to add a game's RetroAchievements set.
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "pass" 2>nul
    if errorlevel 1 (
        echo The .venv folder is from somewhere else; repairing it...
        call :makevenv
        if errorlevel 1 goto nopython
    )
) else (
    echo Making the Python environment in .venv...
    call :makevenv
    if errorlevel 1 goto nopython
)

echo Installing the packages DSiRPC needs...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo Installing the packages failed; see the messages above.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" dsirpc.py setup
exit /b %errorlevel%

:makevenv
py -3 -m venv .venv 2>nul
if not errorlevel 1 exit /b 0
python -m venv .venv
exit /b %errorlevel%

:nopython
echo Python 3 doesn't seem to be installed. Get it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in its installer, then run Setup.bat again.
pause
exit /b 1

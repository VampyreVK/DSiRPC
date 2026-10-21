@echo off
rem Builds the console's two files with Docker (docs\DEVELOPMENT.md, section 4)
rem and puts them in this folder's "SD card\DSiRPC", where DSiRPC run from here
rem offers them to the launcher as an update. Docker Desktop has to be running.
rem
rem   BuildConsole.bat                 builds both files
rem   BuildConsole.bat "C:\...\DSiRPC"  also copies them into that DSiRPC
rem                                    folder (a download you run DSiRPC from)
setlocal
cd /d "%~dp0"

echo Building the launcher...
docker run --rm -v "%CD%\launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest || goto :failed

echo.
echo Building nds-bootstrap (a few minutes)...
docker run --rm -v "%CD%\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 bash -c "sed -i '/security/d' /etc/apt/sources.list && apt-get update && apt-get install -y gcc && gcc lzss.c -o /usr/local/bin/lzss && make nightly" || goto :failed

call :copy_to "%CD%" || goto :failed
if not "%~1"=="" (
    call :copy_to "%~1" || goto :failed
)

echo.
echo Done. Start the launcher while DSiRPC runs and it offers the new files.
pause
exit /b 0

:copy_to
if not exist "%~1\SD card\DSiRPC" mkdir "%~1\SD card\DSiRPC" || exit /b 1
copy /y "launcher\dsirpc-launcher.nds" "%~1\SD card\DSiRPC\dsirpc-launcher.nds" >nul || exit /b 1
copy /y "nds-bootstrap\retail\bin\nds-bootstrap-nightly.nds" "%~1\SD card\DSiRPC\nds-bootstrap-dsirpc.nds" >nul || exit /b 1
echo Copied both files to "%~1\SD card\DSiRPC"
exit /b 0

:failed
echo.
echo It didn't work (is Docker Desktop running?). The messages above say more.
pause
exit /b 1

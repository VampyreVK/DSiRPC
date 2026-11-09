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
rem The version its in-game menu shows. nds-bootstrap's arm9/Makefile asks git,
rem but git can't see this repo from inside Docker (only nds-bootstrap\ is
rem mounted), so it's worked out here the same way: the tag if this commit has
rem one, else the last tag and the commit (at most 19 characters).
set "GIT_VER=dev"
for /f "delims=" %%v in ('git describe --tags --abbrev^=0 2^>nul') do set "GIT_VER=%%v"
git describe --tags --exact-match >nul 2>&1 || for /f "delims=" %%v in ('git rev-parse --short^=7 HEAD 2^>nul') do set "GIT_VER=%GIT_VER%-%%v"
echo Version: %GIT_VER%
docker run --rm -v "%CD%\nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 bash -c "sed -i '/security/d' /etc/apt/sources.list && apt-get update && apt-get install -y gcc && gcc lzss.c -o /usr/local/bin/lzss && make nightly GIT_VER=%GIT_VER%" || goto :failed

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

@echo off
setlocal

echo ========================================================
echo  Havano POS - Production Hang Watchdog (Sysinternals)
echo ========================================================
echo.

:: Ensure dump directory exists
if not exist "C:\PosDumps" (
    echo Creating directory C:\PosDumps ...
    mkdir "C:\PosDumps"
)

:: Check if procdump exists in PATH or current directory
where procdump.exe >nul 2>nul
if %ERRORLEVEL% neq 0 (
    if not exist "%~dp0procdump.exe" (
        echo [ERROR] procdump.exe was not found in PATH or the current folder.
        echo Please download ProcDump from Microsoft Sysinternals:
        echo https://learn.microsoft.com/en-us/sysinternals/downloads/procdump
        echo and place procdump.exe in this folder or in C:\Windows\System32.
        echo.
        pause
        exit /b 1
    )
    set PROCDUMP="%~dp0procdump.exe"
) else (
    set PROCDUMP=procdump.exe
)

:: Choose target process
set TARGET_EXE=HavanoPOS.exe
if "%1"=="python" set TARGET_EXE=python.exe
if "%1"=="dev" set TARGET_EXE=python.exe

echo Target: %TARGET_EXE%
echo Dumps Output Directory: C:\PosDumps\
echo.
echo Starting ProcDump Watchdog for UI hangs / unresponsiveness...
echo (Dump will be generated immediately if the window becomes "Not Responding" for >= 5s)
echo.

%PROCDUMP% -accepteula -h -ma -w %TARGET_EXE% C:\PosDumps\

echo.
pause

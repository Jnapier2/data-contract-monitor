@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ROOT=%~dp0"
set "LAUNCHER=%ROOT%tools\launch.bat"

if not exist "%LAUNCHER%" goto :not_extracted
call "%LAUNCHER%" test
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (echo [OK] Automated tests finished.) else (echo [ERROR] Automated tests finished. Exit code %RC%.)
echo Startup status: "%ROOT%LATEST_LAUNCH_STATUS.txt"
echo Bootstrap log: "%ROOT%logs\bootstrap.log"
if /I not "%DCM_NO_PAUSE%"=="1" pause
exit /b %RC%

:not_extracted
echo.
echo [ERROR] This BAT cannot find the rest of Data Contract Monitor.
echo The most common cause is launching directly inside the downloaded ZIP.
echo Extract the entire ZIP to a normal folder, then run this BAT from the extracted folder.
echo.
if /I not "%DCM_NO_PAUSE%"=="1" pause
exit /b 4

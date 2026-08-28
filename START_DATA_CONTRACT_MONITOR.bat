@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ROOT=%~dp0"
set "LAUNCHER=%ROOT%tools\launch.bat"

if not exist "%LAUNCHER%" goto :not_extracted
call "%LAUNCHER%" serve
set "RC=%ERRORLEVEL%"

if "%RC%"=="0" exit /b 0
if "%RC%"=="130" exit /b 130
echo.
echo [ERROR] Data Contract Monitor did not start.
if exist "%ROOT%LATEST_LAUNCH_STATUS.txt" type "%ROOT%LATEST_LAUNCH_STATUS.txt"
echo.
echo Keep this window or send the files listed above for diagnosis.
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

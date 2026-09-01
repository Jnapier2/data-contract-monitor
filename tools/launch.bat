@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "ACTION=%~1"
if not defined ACTION set "ACTION=serve"
set "STATUS_FILE=%ROOT%\LATEST_LAUNCH_STATUS.txt"
set "LAUNCH_LOG=%ROOT%\logs\launcher.log"

rem Prevent inherited Python settings from redirecting this project into another environment.
set "PYTHONPATH="
set "PYTHONHOME="

if not exist "%ROOT%\VERSION.txt" goto :invalid_root
if not exist "%ROOT%\tools\bootstrap.py" goto :invalid_root

for %%D in (logs state temp cache exports diagnostics reports downloads config backups) do (
  if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D" >nul 2>&1
)

>"%STATUS_FILE%" (
  echo Data Contract Monitor startup status
  echo Project root: %ROOT%
  echo Action: %ACTION%
  echo Started: %DATE% %TIME%
  echo State: locating-compatible-python
)

>>"%LAUNCH_LOG%" echo.
>>"%LAUNCH_LOG%" echo ============================================================
>>"%LAUNCH_LOG%" echo Launch started: %DATE% %TIME%
>>"%LAUNCH_LOG%" echo Project root: %ROOT%
>>"%LAUNCH_LOG%" echo Action: %ACTION%

call :select_python
if errorlevel 1 goto :python_missing

>>"%LAUNCH_LOG%" echo Python command: %PYTHON_CMD%
%PYTHON_CMD% -c "import platform,sys; print('Selected Python:', sys.executable); print('Version:', platform.python_version()); print('Architecture:', platform.architecture()[0])" >>"%LAUNCH_LOG%" 2>&1

rem Support export is deliberately available even when release integrity fails.
if /I "%ACTION%"=="export" goto :run_export

rem Reconcile only verified, recognized prior-version application wheels before the strict gate.
%PYTHON_CMD% "%ROOT%\tools\maintenance_preflight.py" --root "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :maintenance_failed

%PYTHON_CMD% "%ROOT%\tools\release_gate.py" --root "%ROOT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :release_failed

if /I "%ACTION%"=="repair" goto :run_repair

%PYTHON_CMD% "%ROOT%\tools\bootstrap.py" --root "%ROOT%" --action "%ACTION%"
set "RC=%ERRORLEVEL%"
goto :finish

:run_repair
%PYTHON_CMD% "%ROOT%\tools\bootstrap.py" --root "%ROOT%" --action doctor --repair
set "RC=%ERRORLEVEL%"
goto :finish

:run_export
%PYTHON_CMD% "%ROOT%\tools\support_export.py" --root "%ROOT%"
set "RC=%ERRORLEVEL%"
goto :finish

:maintenance_failed
>>"%STATUS_FILE%" echo State: maintenance-preflight-failed
>>"%STATUS_FILE%" echo Exit code: %RC%
>>"%STATUS_FILE%" echo Recovery: run CREATE_SUPPORT_EXPORT.bat, then use a fresh extracted release copy.
>>"%LAUNCH_LOG%" echo Maintenance preflight failed with exit code %RC%.
goto :show_failure

:release_failed
>>"%STATUS_FILE%" echo State: release-integrity-failed
>>"%STATUS_FILE%" echo Exit code: %RC%
>>"%STATUS_FILE%" echo Recovery: run CREATE_SUPPORT_EXPORT.bat, then use REPAIR_INSTALLATION.bat or a fresh extracted release copy.
>>"%LAUNCH_LOG%" echo Release gate failed with exit code %RC%.
goto :show_failure

:python_missing
set "RC=4"
>"%ROOT%\logs\python_detection.txt" (
  echo Python detection captured: %DATE% %TIME%
  echo Required: standard 64-bit CPython 3.11, 3.12, 3.13, or 3.14
  echo Free-threaded Python builds are not used by this release.
  echo.
  echo --- where py ---
  where py 2^>nul
  echo.
  echo --- where python ---
  where python 2^>nul
  echo.
  echo --- py --list ---
  py --list 2^>nul
)
>>"%STATUS_FILE%" echo State: compatible-python-not-found
>>"%STATUS_FILE%" echo Exit code: 4
>>"%STATUS_FILE%" echo Recovery: install standard 64-bit Python 3.13 or 3.14, then run this BAT again.
echo.
echo [ERROR] A compatible standard 64-bit Python runtime was not found.
echo Data Contract Monitor supports standard 64-bit Python 3.11 through 3.14.
echo Install standard 64-bit Python 3.13 or 3.14, then run this file again.
echo Detection details: "%ROOT%\logs\python_detection.txt"
goto :show_failure

:invalid_root
set "RC=4"
echo.
echo [ERROR] The project files are incomplete or this BAT was launched from inside the ZIP.
echo Extract the entire ZIP to a normal folder before launching it.
echo.
goto :show_failure

:finish
if "%RC%"=="0" (
  >>"%STATUS_FILE%" echo State: completed
  >>"%STATUS_FILE%" echo Exit code: 0
  >>"%STATUS_FILE%" echo Finished: %DATE% %TIME%
  >>"%LAUNCH_LOG%" echo Action completed successfully.
  if /I not "%DCM_NO_PAUSE%"=="1" if /I not "%ACTION%"=="serve" pause
  exit /b 0
)
if "%RC%"=="130" (
  >>"%STATUS_FILE%" echo State: stopped-by-user
  >>"%STATUS_FILE%" echo Exit code: 130
  >>"%STATUS_FILE%" echo Finished: %DATE% %TIME%
  >>"%LAUNCH_LOG%" echo Action stopped by user.
  exit /b 130
)
>>"%STATUS_FILE%" echo State: failed
>>"%STATUS_FILE%" echo Exit code: %RC%
>>"%STATUS_FILE%" echo Finished: %DATE% %TIME%
>>"%LAUNCH_LOG%" echo Action failed with exit code %RC%.

:show_failure
echo.
echo Startup status: "%STATUS_FILE%"
echo Bootstrap log: "%ROOT%\logs\bootstrap.log"
echo Launcher log: "%LAUNCH_LOG%"
if /I not "%DCM_NO_PAUSE%"=="1" pause
exit /b %RC%

:select_python
set "PYTHON_CMD="
rem Repair/export intentionally use an external runtime so a broken/stale project venv cannot block recovery.
if /I "%ACTION%"=="repair" goto :external_python
if /I "%ACTION%"=="export" goto :external_python
if exist "%ROOT%\.venv\Scripts\python.exe" (
  call :probe_python "%ROOT%\.venv\Scripts\python.exe"
  if not errorlevel 1 exit /b 0
)
:external_python
call :probe_python py -3.13
if not errorlevel 1 exit /b 0
call :probe_python py -3.14
if not errorlevel 1 exit /b 0
call :probe_python py -3.12
if not errorlevel 1 exit /b 0
call :probe_python py -3.11
if not errorlevel 1 exit /b 0
call :probe_python python
if not errorlevel 1 exit /b 0
if defined LocalAppData (
  call :probe_python "%LocalAppData%\Programs\Python\Python313\python.exe"
  if not errorlevel 1 exit /b 0
  call :probe_python "%LocalAppData%\Programs\Python\Python314\python.exe"
  if not errorlevel 1 exit /b 0
  call :probe_python "%LocalAppData%\Python\pythoncore-3.13-64\python.exe"
  if not errorlevel 1 exit /b 0
  call :probe_python "%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
  if not errorlevel 1 exit /b 0
)
exit /b 1

:probe_python
%* -c "import struct,sys,sysconfig; v=sys.version_info[:2]; ok=(3,11) <= v <= (3,14) and struct.calcsize('P') == 8 and not bool(sysconfig.get_config_var('Py_GIL_DISABLED')); raise SystemExit(0 if ok else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYTHON_CMD=%*"
exit /b 0

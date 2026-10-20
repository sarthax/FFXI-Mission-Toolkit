@echo off
cd /d "%~dp0"

REM Uses this toolkit's own dedicated .venv (see setup.bat) instead of the system Python.
set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" (
    echo No .venv found yet -- run setup.bat first.
    pause
    exit /b 1
)

if not exist "ffxi_zone_database.db" (
    echo No database found yet -- run setup.bat first.
    pause
    exit /b 1
)

"%PY%" -c "import xi_tinkerer" 2>nul
if errorlevel 1 (
    echo [ERROR] The "xi_tinkerer" component is missing or was never installed.
    echo Run setup.bat -- it will tell you exactly how to install it.
    pause
    exit /b 1
)

echo Starting the Mission Toolkit...
echo Once you see "Uvicorn running on http://127.0.0.1:8420", open that address
echo in your web browser. Close this window to stop the server.
echo.
REM Optional supervisor credentials/settings stay outside Git and are never loaded by default.
REM Only an explicit MISSION_TOOLKIT_ENV_PS1 file opts into the local gateway.
if not defined MISSION_TOOLKIT_ENV_PS1 goto standard_start
if not exist "%MISSION_TOOLKIT_ENV_PS1%" (
    echo [ERROR] Configured supervisor settings file was not found.
    pause
    exit /b 1
)
REM Avoid interpolating the file path into the PowerShell command (quotes/metacharacters).
set "MISSION_TOOLKIT_PYTHON=%PY%"
powershell -NoProfile -Command "& { . $env:MISSION_TOOLKIT_ENV_PS1; if ($?) { & $env:MISSION_TOOLKIT_PYTHON -m workbench.app.host } else { exit 1 } }"
goto end_start

:standard_start
"%PY%" -m workbench.app.host

:end_start
pause

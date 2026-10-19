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
REM Optional local supervisor settings (token, results DB, read-only DB account) live OUTSIDE the repo.
REM Override the location with MISSION_TOOLKIT_ENV_PS1. Without the file the supervisor gateway stays disabled.
if "%MISSION_TOOLKIT_ENV_PS1%"=="" set MISSION_TOOLKIT_ENV_PS1=D:\MissionToolkitData\supervisor.env.ps1
if exist "%MISSION_TOOLKIT_ENV_PS1%" (
    echo Loading supervisor settings from %MISSION_TOOLKIT_ENV_PS1%
    if exist "D:\MissionToolkitData\extra_site" set PYTHONPATH=D:\MissionToolkitData\extra_site;%PYTHONPATH%
    powershell -NoProfile -ExecutionPolicy Bypass -Command ". '%MISSION_TOOLKIT_ENV_PS1%'; & '%PY%' -m workbench.app.host"
) else (
    echo No supervisor env file found -- supervisor gateway disabled.
    "%PY%" -m workbench.app.host
)
pause

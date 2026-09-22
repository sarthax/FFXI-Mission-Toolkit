@echo off
cd /d "%~dp0"

REM 2026-09-08: uses this toolkit's own dedicated .venv (see setup.bat) instead of the system
REM Python -- one of this toolkit's real dependencies (luaparser) permanently conflicts with
REM other real packages a system-wide Python install might already have, so its dependencies only
REM ever get installed into this isolated environment, never system-wide.
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
"%PY%" gui_server.py
pause

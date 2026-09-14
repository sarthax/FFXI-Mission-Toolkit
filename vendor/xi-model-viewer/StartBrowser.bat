@echo off
REM XI Model Viewer - browser dev mode (no Tauri/Rust/Visual Studio needed).
REM   Starts the two real, already-existing pieces this mode needs together:
REM     1) scripts/serve.py  -- the /fs file-read backend (py -3, stdlib only)
REM     2) ui's Vite dev server -- the actual app, proxying /fs to (1)
REM   This is what Mission Toolkit's own "view 3D model" links (Entity Lookup,
REM   http://localhost:5173/?npc=<file_id>) expect running. For the full
REM   desktop app instead, use Start.bat (needs Rust + Tauri CLI).
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist "ui\node_modules" (
    echo Installing frontend dependencies ^(one-time^)...
    pushd ui
    call npm install || goto :error
    popd
)

echo Starting the /fs backend on :8766 ...
start "XI Model Viewer - backend (:8766)" cmd /k py -3 scripts\serve.py 8766

echo Starting the Vite dev server on :5173 ...
pushd ui
start "XI Model Viewer - frontend (:5173)" cmd /k npm run dev
popd

echo.
echo Both started in their own windows. Close either window (or Ctrl+C in it)
echo to stop that half. Open http://localhost:5173/ once Vite reports ready,
echo or just click a "view 3D model" link from Mission Toolkit's Entity Lookup.
exit /b 0

:error
echo.
echo Setup failed -- make sure Node.js and Python are on PATH.
pause
exit /b 1

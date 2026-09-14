@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo  FFXI Mission Toolkit - First-Time Setup
echo ============================================
echo.

REM --- 1. Check Python is installed and on PATH ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on your PATH.
    echo.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo During install, check the box "Add python.exe to PATH".
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

REM --- 1b. Create (or reuse) a dedicated virtual environment ---
REM 2026-09-08: real fix -- this toolkit used to install straight into the system Python. That's
REM fine in isolation, but one of its real dependencies (luaparser, needed for the event
REM decompiler) permanently pins antlr4-python3-runtime==4.13.2, which conflicts with at least one
REM other real, unrelated package (omegaconf) some users' system Python already has, needing
REM ==4.9.*  -- confirmed live, no luaparser version avoids this pin. A dedicated .venv means this
REM toolkit's own dependencies can never break something else already on your machine, and vice
REM versa. If this is the first run, this step also downloads xi_tinkerer/other packages into a
REM fresh environment -- expect it to take a little longer than a bare `pip install` would.
set VENV_DIR=%~dp0.venv
set PY=%VENV_DIR%\Scripts\python.exe
if not exist "%PY%" (
    echo Creating a dedicated Python environment for this toolkit ^(.venv\^)...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment -- see the output above.
        pause
        exit /b 1
    )
)

REM --- 2. Load previously saved paths, if any ---
set CONFIG_FILE=%~dp0toolkit_config.txt
set FFXI_PATH=
set TOPAZ_PATH=
if exist "%CONFIG_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%CONFIG_FILE%") do (
        if "%%A"=="FFXI_PATH" set FFXI_PATH=%%B
        if "%%A"=="TOPAZ_PATH" set TOPAZ_PATH=%%B
    )
)

REM --- 3. Ask for anything not already saved ---
if "%FFXI_PATH%"=="" (
    echo Enter the full path to your FFXI client install.
    echo   This is the folder containing FFXiMain.dll
    echo   Example: C:\SquareEnix\FINAL FANTASY XI
    set /p FFXI_PATH="FFXI install path: "
)

if "%TOPAZ_PATH%"=="" (
    echo.
    echo Enter the full path to your Topaz server checkout ^(OPTIONAL -- only needed for
    echo the backport/ID Drift module^). Press Enter to skip if you don't do backport work;
    echo you can set this later from the Settings page.
    echo   This is the folder containing conf\map.conf
    echo   Example: C:\topaz
    set /p TOPAZ_PATH="Topaz server path (optional, Enter to skip): "
)

REM --- 4. Save for next time ---
> "%CONFIG_FILE%" (
    echo FFXI_PATH=%FFXI_PATH%
    echo TOPAZ_PATH=%TOPAZ_PATH%
)
echo.
echo Saved your paths to toolkit_config.txt -- delete that file if you ever need
echo to change them (this script will ask again next run).
echo.

REM --- 5. Install required Python packages ---
echo Installing required Python packages...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Installing packages failed -- see the output above for details.
    pause
    exit /b 1
)

REM --- 6. Install xi_tinkerer (a compiled tool, not a normal package from pip) ---
REM Required -- the toolkit will not start at all without it (gui_server.py imports it directly).
REM install_xi_tinkerer.py downloads the real wheel straight from its GitHub release --
REM no manual download needed unless that fails (e.g. no internet access).
echo.
echo Checking for the xi_tinkerer component...
%PY% install_xi_tinkerer.py
if errorlevel 1 (
    echo.
    echo [ERROR] Could not install xi_tinkerer automatically. The toolkit cannot
    echo start without it -- this is required, not optional. To install it by hand:
    echo   1. Go to https://github.com/sruon/xi-tinkerer-py/releases
    echo   2. Download the .whl file matching your Python version and Windows
    echo   3. Run: .venv\Scripts\python.exe -m pip install path\to\the\downloaded\file.whl
    echo   4. Run setup.bat again.
    echo.
    pause
    exit /b 1
)

REM --- 7. Save the same paths into the toolkit's own settings, so the web pages match ---
%PY% -c "import settings, sqlite3; con = sqlite3.connect(str(settings.DB_PATH)); settings.set_many(con, {'ffxi_install_path': r'%FFXI_PATH%', 'topaz_server_path': r'%TOPAZ_PATH%'}); con.close()"

REM --- 8. Optional tools/data for the core module, ID Drift, and Events pages -- each is a real
REM download from its own GitHub/public-bucket source (install_external_tools.py), same
REM "auto-download, tell you if it fails" pattern as xi_tinkerer above. None of these block setup
REM if they fail (no internet, GitHub down, etc) -- the affected homepage rows just show their own
REM "Install" button instead, same as if you'd skipped this step and clicked it there later.
REM
REM IMPORTANT: this must run BEFORE build_database.py/build_sql_index.py below -- FFXI-DATS feeds
REM build_database.py's door/prop/elevator/zone-line tables, FFXI-Resources-dist feeds its
REM items_external/keyitems_external tables, and LandSandBoat/sql is what build_sql_index.py (the
REM core module's required SQL indexer) now parses instead of a Topaz server. Fetching these first
REM means one pass of the build steps below picks up everything instead of needing a manual
REM "Rebuild" click afterward.
echo.
echo Installing optional tools/data (xi-tinkerer-cli, FFXI-DATS, FFXI-Resources, LandSandBoat)...
echo   these are large downloads (LandSandBoat ~180MB, FFXI-DATS ~200MB) -- this may take a while
%PY% install_external_tools.py xi-tinkerer-cli
%PY% install_external_tools.py ffxi-dats
%PY% install_external_tools.py ffxi-resources-dist
%PY% install_external_tools.py landsandboat-full

REM --- 9. Build the zone database ---
echo.
echo Building the zone database (usually under a minute)...
%PY% build_database.py --ffxi-path "%FFXI_PATH%"

REM --- 10. Index NPC names and dialog text for every zone (slower -- reads real client data) ---
echo.
echo Indexing NPC names for every zone (this can take a few minutes)...
%PY% build_npc_index.py --all --ffxi-path "%FFXI_PATH%"

echo.
echo Indexing dialog text for every zone (this can take a few minutes)...
%PY% build_dialog_index.py --all --quiet --ffxi-path "%FFXI_PATH%"

REM --- 11. Create remaining tables the web pages expect (Assault mission text, key items) ---
REM Real source data for these (MassExtractor_output/) isn't bundled -- see SETUP.md. This just
REM creates the tables so the pages don't error; they'll show 0 entries until that data exists.
echo.
echo Setting up remaining reference tables...
%PY% ingest_global_tables.py --ffxi-path "%FFXI_PATH%"
%PY% build_capture_index.py list >nul

REM --- 12. Index the bundled LandSandBoat checkout's own SQL (npc_list, mob_spawn_points, etc) --
REM this is the core module's primary data source (LSB-primary), required, not optional. If step 8
REM couldn't fetch LandSandBoat (no internet access during setup), this just indexes 0 rows -- use
REM the "Install" button on the homepage's "Your LSB server's own SQL" row to fetch it later.
echo.
echo Indexing the bundled LandSandBoat checkout's SQL data...
%PY% build_sql_index.py

REM --- 13. Cross-reference LandSandBoat vs your Topaz server (ID Drift page) -- only meaningful
REM once LandSandBoat/ actually exists (step 8 just fetched it, or you placed it yourself).
if exist "%~dp0LandSandBoat\sql" (
    echo.
    echo Indexing LandSandBoat cross-reference data...
    %PY% build_lsb_index.py
) else (
    echo.
    echo Skipping LandSandBoat cross-reference indexing -- LandSandBoat/ wasn't fetched
    echo ^(no internet access during setup?^). Use the "Install" button on the homepage's
    echo "LandSandBoat cross-reference" row to fetch it later, or place it yourself at:
    echo   %~dp0LandSandBoat
)

REM --- 14. BG Wiki page dump -- ships pre-bundled (ffxi-wiki-dumps-dist\bg-wiki.jsonl.gz), so this
REM is just a quick incremental sync to catch anything the wiki has changed since that snapshot
REM was taken. Never blocks setup -- if it fails, the homepage's own "Rebuild" button retries it.
echo.
echo Syncing BG Wiki data (incremental -- only pages changed since the bundled snapshot)...
%PY% scrape_bg_wiki.py

echo.
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo Everything above builds and refreshes itself from the homepage's own "Rebuild"/"Install"
echo buttons any time later -- nothing here needs to be run by hand again.
echo.
call "%~dp0start.bat"

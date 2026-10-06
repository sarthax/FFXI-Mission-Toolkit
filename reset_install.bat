@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Mission Toolkit - Reset to clean install
echo ============================================
echo.
echo This deletes the database, LandSandBoat/FFXI-DATS/FFXI-Resources-dist checkouts,
echo generated reports, and other fetched/generated data -- see DIST_PACKAGING.md for the
echo exact list. Nothing hand-authored (source, templates, docs, setup.bat) is touched.
echo Everything deleted is re-fetched/rebuilt by setup.bat or the homepage's own
echo Rebuild/Install buttons.
echo.
echo First, a dry run showing exactly what would be deleted:
echo.
python scripts\bootstrap\reset_install.py
if errorlevel 1 (
    echo.
    echo [ERROR] scripts\bootstrap\reset_install.py failed -- see the output above.
    pause
    exit /b 1
)

echo.
set /p CONFIRM="Type YES (all caps) to actually delete the above, anything else cancels: "
if not "%CONFIRM%"=="YES" (
    echo.
    echo Cancelled -- nothing was deleted.
    pause
    exit /b 0
)

echo.
python scripts\bootstrap\reset_install.py --i-am-sure
echo.
echo Done. Run setup.bat to rebuild a fresh install.
pause

@echo off
rem ===========================================================================
rem  build_windows.bat  --  one-shot Windows build for PeopleFinder
rem                        (frozen app + embedded Elasticsearch + tc_index data).
rem
rem  Produces:  packaging\Output\PeopleFinder-Setup.exe
rem
rem  Steps:
rem    1. build virtual-env + build dependencies (PySide6, elasticsearch, pyinstaller)
rem    2. verify  runtime\elasticsearch\   (the bundled ES distribution, incl. jdk/)
rem    3. verify  runtime\es-data\          (the ~22 GB tc_index data directory)
rem    4. render the app icon                (packaging\app.ico)
rem    5. freeze the app + bundle Elasticsearch with PyInstaller  (packaging\dist\)
rem    6. build the installer with Inno Setup                     (packaging\Output\)
rem
rem  Build-machine prerequisites (NOT the end user):
rem    * Windows x64, Python 3.10-3.12 on PATH
rem    * Inno Setup 6.3+   (https://jrsoftware.org/isdl.php)
rem    * runtime\elasticsearch\  and  runtime\es-data\  prepared beforehand
rem      (see packaging\README.md, tools\prepare_es_payload.py,
rem       packaging\configure_bundled_es.py)
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "PKG_DIR=%~dp0"
pushd "%PKG_DIR%.." || (echo Could not enter project root.& exit /b 1)
set "ROOT=%CD%"
echo Project root: %ROOT%

rem --- 1. build virtual-env -------------------------------------------------
set "VENV=%ROOT%\.build-venv"
if not exist "%VENV%\Scripts\python.exe" (
    echo.
    echo [1/6] Creating build virtual-env "%VENV%" ...
    python -m venv "%VENV%" || (echo Failed to create venv.& goto :fail)
)
set "PY=%VENV%\Scripts\python.exe"
echo [1/6] Installing build dependencies ...
"%PY%" -m pip install --upgrade pip                  || goto :fail
"%PY%" -m pip install -r "%ROOT%\requirements.txt"   || goto :fail
"%PY%" -m pip install "pyinstaller>=6.3"             || goto :fail

rem --- 2. verify bundled Elasticsearch distribution -------------------------
echo.
echo [2/6] Checking runtime\elasticsearch ...
if not exist "%ROOT%\runtime\elasticsearch\bin\elasticsearch.bat" (
    echo.
    echo  ====================================================================
    echo   runtime\elasticsearch\ is missing (or not an ES distribution).
    echo.
    echo   1) Download an Elasticsearch distribution that matches your source
    echo      cluster's version (Windows .zip, which includes its own jdk\),
    echo      and extract it to:   %ROOT%\runtime\elasticsearch\
    echo   2) Configure it for bundling:
    echo        "%PY%" packaging\configure_bundled_es.py --es-home runtime\elasticsearch
    echo      (add  --set-password --data-dir runtime\es-data  if your data
    echo       payload came from a snapshot rather than a cold copy.)
    echo  ====================================================================
    goto :fail
)

rem --- 3. verify the tc_index data payload ----------------------------------
echo.
echo [3/6] Checking runtime\es-data ...
if not exist "%ROOT%\runtime\es-data" (
    echo.
    echo  ====================================================================
    echo   runtime\es-data\ is missing.  Build it from your live tc_index, e.g.
    echo   (simplest - stop your source ES first):
    echo.
    echo     "%PY%" tools\prepare_es_payload.py --mode cold-copy ^
    echo         --source-data  "C:\path\to\elasticsearch\data" ^
    echo         --source-config "C:\path\to\elasticsearch\config" ^
    echo         --out runtime\es-data --es-home runtime\elasticsearch --verify
    echo  ====================================================================
    goto :fail
)
rem crude "is it big enough to be real?" check (look for a Lucene index file)
dir /b /s "%ROOT%\runtime\es-data\*.cfs" "%ROOT%\runtime\es-data\*.si" >nul 2>nul || (
    echo   WARNING: runtime\es-data looks empty/incomplete - no Lucene segment files found.
    echo            Continuing anyway, but the app will have no data to search.
)
for /f "tokens=3" %%S in ('dir /-c /s "%ROOT%\runtime\es-data" ^| find "File(s)"') do set "DATASIZE=%%S"
echo       runtime\es-data size: %DATASIZE% bytes

rem --- 4. icon --------------------------------------------------------------
echo.
echo [4/6] Rendering application icon ...
"%PY%" "%ROOT%\packaging\make_icon.py" || echo (icon generation failed - continuing without a custom .ico)

rem --- 5. PyInstaller -------------------------------------------------------
echo.
echo [5/6] Freezing the app + bundling Elasticsearch (PyInstaller) ...
rmdir /s /q "%ROOT%\packaging\dist"  2>nul
rmdir /s /q "%ROOT%\packaging\build" 2>nul
"%PY%" -m PyInstaller "%ROOT%\packaging\PeopleFinder.spec" --noconfirm ^
       --distpath "%ROOT%\packaging\dist" --workpath "%ROOT%\packaging\build" || goto :fail
if not exist "%ROOT%\packaging\dist\PeopleFinder\PeopleFinder.exe"           ( echo PyInstaller produced no executable.& goto :fail )
if not exist "%ROOT%\packaging\dist\PeopleFinder\elasticsearch\bin\elasticsearch.bat" ( echo Bundled Elasticsearch missing from the build.& goto :fail )

rem --- 6. Inno Setup --------------------------------------------------------
echo.
echo [6/6] Building the Windows installer (Inno Setup) ...
set "ISCC="
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
) do if exist "%%~P" set "ISCC=%%~P"
where ISCC.exe >nul 2>nul && for /f "delims=" %%P in ('where ISCC.exe') do set "ISCC=%%P"
if not defined ISCC (
    echo.
    echo  Inno Setup compiler (ISCC.exe) not found.  Install Inno Setup 6.3+
    echo  (https://jrsoftware.org/isdl.php) and re-run, or compile manually:
    echo     ISCC.exe "%ROOT%\packaging\installer.iss"
    goto :fail
)
echo       using: "%ISCC%"
"%ISCC%" "%ROOT%\packaging\installer.iss" || goto :fail

echo.
echo ===========================================================================
echo  DONE.  Installer created at:
echo     %ROOT%\packaging\Output\PeopleFinder-Setup.exe
echo ===========================================================================
popd
endlocal
exit /b 0

:fail
echo.
echo *** BUILD FAILED ***
popd
endlocal
exit /b 1

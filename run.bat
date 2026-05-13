@echo off
rem ---------------------------------------------------------------------------
rem Convenience launcher (Windows).
rem   * activates .\venv (or .\.venv) if it exists
rem   * starts the desktop application
rem Usage:  run.bat
rem ---------------------------------------------------------------------------
setlocal

cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

python main.py %*
exit /b %ERRORLEVEL%
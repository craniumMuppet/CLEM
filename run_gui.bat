@echo off
setlocal
cd /d "%~dp0"

set "CLEM_BOOTSTRAP_PYTHON="
where py.exe >nul 2>nul
if %errorlevel%==0 set "CLEM_BOOTSTRAP_PYTHON=py.exe -3"
if not defined CLEM_BOOTSTRAP_PYTHON where python.exe >nul 2>nul && set "CLEM_BOOTSTRAP_PYTHON=python.exe"
if not defined CLEM_BOOTSTRAP_PYTHON (
    echo CLEM requires Python 3.12 or newer, but Python was not found.
    pause
    exit /b 1
)

%CLEM_BOOTSTRAP_PYTHON% "%~dp0bootstrap_runtime.py"
if errorlevel 1 (
    echo.
    echo CLEM could not install its runtime dependencies.
    echo Review the error above, then run run_gui.bat again.
    pause
    exit /b 1
)

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "CLEM GUI" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch_gui.pyw"
    exit /b 0
)

rem Console fallback keeps the traceback visible if pythonw is unavailable.
"%~dp0.venv\Scripts\python.exe" "%~dp0climate_model_gui.py"
exit /b %errorlevel%

@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>nul
if %errorlevel%==0 (
    py.exe -3 "%~dp0climate_model_gui.py"
) else (
    python.exe "%~dp0climate_model_gui.py"
)

if not %errorlevel%==0 (
    echo.
    echo The GUI failed. Review the traceback above or gui_startup_error.log.
    pause
)
exit /b %errorlevel%

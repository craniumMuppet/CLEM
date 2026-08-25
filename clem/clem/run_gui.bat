@echo off
setlocal
cd /d "%~dp0"

rem Prefer the Windows Python launcher so the selected interpreter is explicit.
where pyw.exe >nul 2>nul
if %errorlevel%==0 (
    start "EGCM GUI" pyw.exe -3 "%~dp0launch_gui.pyw"
    exit /b 0
)

where pythonw.exe >nul 2>nul
if %errorlevel%==0 (
    start "EGCM GUI" pythonw.exe "%~dp0launch_gui.pyw"
    exit /b 0
)

rem Console fallback keeps the traceback visible when no windowed interpreter exists.
where py.exe >nul 2>nul
if %errorlevel%==0 (
    py.exe -3 "%~dp0climate_model_gui.py"
    exit /b %errorlevel%
)

python.exe "%~dp0climate_model_gui.py"
exit /b %errorlevel%

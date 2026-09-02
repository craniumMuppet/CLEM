@echo off
setlocal
cd /d "%~dp0"

set "CLEM_BOOTSTRAP_PYTHON="
where py.exe >nul 2>nul
if %errorlevel%==0 set "CLEM_BOOTSTRAP_PYTHON=py.exe -3"
if not defined CLEM_BOOTSTRAP_PYTHON set "CLEM_BOOTSTRAP_PYTHON=python.exe"

%CLEM_BOOTSTRAP_PYTHON% "%~dp0bootstrap_runtime.py"
if errorlevel 1 (
    echo.
    echo CLEM dependency setup failed. Review the output above.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" -m streamlit run app.py
exit /b %errorlevel%

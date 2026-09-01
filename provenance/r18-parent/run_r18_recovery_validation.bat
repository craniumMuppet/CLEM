@echo off
setlocal
cd /d "%~dp0"
python verify_r18_local.py --stage recovery
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%

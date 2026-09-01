@echo off
setlocal
cd /d "%~dp0"
python verify_r18_local.py --stage all --timeout 300 --setup-timeout 300
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%

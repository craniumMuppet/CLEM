@echo off
setlocal
cd /d "%~dp0"
python verify_r18_2_seaice_operator.py --stage sea-ice --timeout 300 --setup-timeout 300
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%

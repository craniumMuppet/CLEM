@echo off
setlocal
cd /d "%~dp0"
python verify_r18_2_seaice_operator.py --stage sea-ice
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo R18.2 sea-ice operator validation exited with code %RC%. Re-run this same BAT to resume.
pause
exit /b %RC%

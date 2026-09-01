@echo off
setlocal
cd /d "%~dp0"
python verify_r18_local.py --stage all
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo R18 validation exited with code %RC%. Re-run the same BAT to resume.
pause
exit /b %RC%

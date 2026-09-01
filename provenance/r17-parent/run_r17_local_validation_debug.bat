@echo off
setlocal
cd /d "%~dp0"
call run_r17_local_validation.bat %*
set ERR=%errorlevel%
echo.
echo Exit code: %ERR%
pause
exit /b %ERR%

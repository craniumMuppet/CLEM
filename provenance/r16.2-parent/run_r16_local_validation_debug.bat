@echo off
setlocal
cd /d "%~dp0"
call run_r16_local_validation.bat %*
echo.
echo Exit code: %errorlevel%
pause

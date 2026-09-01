@echo off
setlocal
cd /d "%~dp0"
call run_r16_2_teos_validation.bat %*
set EXITCODE=%errorlevel%
echo.
echo Exit code: %EXITCODE%
pause
exit /b %EXITCODE%

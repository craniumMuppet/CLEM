@echo off
setlocal
cd /d "%~dp0"
echo CLEM v2.13 release consistency check
echo This performs static/setup checks only and advances zero climate years.
python verify_physics_local.py --worker-mode static
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo RELEASE CONSISTENCY CHECK FAILED with exit code %RC%.
) else (
  echo RELEASE CONSISTENCY CHECK PASSED.
)
pause
exit /b %RC%

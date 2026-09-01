@echo off
setlocal
cd /d "%~dp0"
echo Coupled Low-complexity Earth Model v2.29.29 out-of-sample validation
echo Repair-workflow R12 validation design; current v2.29.29 package preserves the validated dynamics through documented evidence inheritance.
echo Runs SSP2-4.5 at 10 and 5 degrees plus 0.1/0.2/0.3 Sv hosing dose response.
echo Every climate child advances at most 5 model years and is checkpointed.
python verify_physics_local.py --validation-only
set ERR=%ERRORLEVEL%
echo.
if %ERR% NEQ 0 (
  echo Validation exited with code %ERR%.
) else (
  echo Validation command finished. See physics_verification_bundle.zip.
)
pause
exit /b %ERR%

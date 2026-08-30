@echo off
setlocal
cd /d "%~dp0"
echo CLEM v2.12 out-of-sample validation - v2.11 physics unchanged
echo Runs SSP2-4.5 at 10 and 5 degrees plus 0.1/0.2/0.3 Sv hosing dose response.
echo Every climate child advances at most 5 model years and is checkpointed.
python verify_physics_local.py --validation-only
set ERR=%ERRORLEVEL%
echo.
if %ERR% NEQ 0 (
  echo Validation exited with code %ERR%.
) else (
  echo Validation command finished. Upload physics_verification_bundle.zip to ChatGPT.
)
pause
exit /b %ERR%

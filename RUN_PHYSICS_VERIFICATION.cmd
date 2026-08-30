@echo off
setlocal
cd /d "%~dp0"

echo Coupled Low-complexity Earth Model local physics verification
echo All model integrations are split into restartable chunks of at most 5 model years.
echo Re-running this file resumes from the latest completed checkpoint.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 verify_physics_local.py
) else (
    python verify_physics_local.py
)

set RC=%errorlevel%
echo.
if %RC%==0 (
    echo Verification command finished. Upload physics_verification_bundle.zip to ChatGPT.
) else (
    echo Verification stopped with exit code %RC%.
    echo The latest completed checkpoint remains available. Run this file again to resume.
)
pause
exit /b %RC%

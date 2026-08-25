@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title EGCM PIOMAS + OSI SAF Data Repair

echo ============================================================
echo EGCM PIOMAS + OSI SAF DATA REPAIR - 2026-08-09
echo ============================================================
echo.
echo This only refreshes the two public products that need repair.
echo No Earthdata token, username, or password is required.
echo Existing CryoSat-2 / ICESat-2 / G02202 data are not redownloaded.
echo The window will stay open on success or failure.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\refresh_piomas_osi.ps1"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo REFRESH COMPLETED SUCCESSFULLY
    echo.
    echo Upload this file to ChatGPT:
    echo   %~dp0ARCTIC_VALIDATION_DATA_BUNDLE_CORRECTED.zip
) else (
    echo REFRESH FAILED - EXIT CODE %RC%
    echo.
    if exist "%~dp0PIOMAS_OSI_REFRESH_LAST_LOG.txt" (
        echo Last log path:
        type "%~dp0PIOMAS_OSI_REFRESH_LAST_LOG.txt"
    ) else (
        echo Look in:
        echo   %~dp0logs\
    )
)
echo ============================================================
echo.
echo This window will NOT close automatically.
pause
exit /b %RC%

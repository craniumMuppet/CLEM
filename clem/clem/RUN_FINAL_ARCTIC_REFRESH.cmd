@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title EGCM Arctic Validation Final Refresh

echo ============================================================
echo EGCM ARCTIC VALIDATION FINAL REFRESH - 2026-08-09
echo ============================================================
echo.
echo This build already contains G02202, CryoSat-2 and ICESat-2 evidence.
echo It only refreshes corrected public PIOMAS and OSI SAF data.
echo It installs pytest automatically and verifies all five core sources.
echo No Earthdata credentials are required.
echo The window will stay open on success or failure.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\refresh_piomas_osi.ps1"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo FINAL REFRESH COMPLETED SUCCESSFULLY
    echo.
    echo Upload this file to ChatGPT:
    echo   %~dp0ARCTIC_VALIDATION_DATA_BUNDLE_CORRECTED.zip
) else (
    echo FINAL REFRESH FAILED - EXIT CODE %RC%
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

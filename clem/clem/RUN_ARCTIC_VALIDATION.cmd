@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title EGCM Arctic Validation Acquisition

echo ============================================================
echo EGCM ARCTIC DATA ACQUISITION - CORE 5 CONTINUE BUILD
echo ============================================================
echo.
echo This window will remain open whether the run succeeds or fails.
echo A complete log is written under the logs folder.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\acquire_arctic_validation_stack.ps1"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo ACQUISITION COMPLETED SUCCESSFULLY
    echo.
    echo Upload this file to ChatGPT:
    echo   %~dp0ARCTIC_VALIDATION_DATA_BUNDLE.zip
) else (
    echo ACQUISITION FAILED - EXIT CODE %RC%
    echo.
    echo The error has been saved to a log file.
    if exist "%~dp0ARCTIC_ACQUISITION_LAST_LOG.txt" (
        echo Last log path:
        type "%~dp0ARCTIC_ACQUISITION_LAST_LOG.txt"
    ) else (
        echo Look in:
        echo   %~dp0logs\
    )
    echo.
    echo Send that log file to ChatGPT.
)
echo ============================================================
echo.
echo This window will NOT close automatically.
echo Press any key only after you have read or copied the result.
pause >nul

exit /b %RC%

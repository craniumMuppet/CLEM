@echo off
setlocal
cd /d "%~dp0"
rem Sea-ice stage does not require GSW.
python verify_r17_local.py --stage sea-ice %*
exit /b %errorlevel%

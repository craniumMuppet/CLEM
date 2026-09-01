@echo off
setlocal
cd /d "%~dp0"
rem Recovery/hysteresis stage uses the validated linear EOS and does not require GSW.
python verify_r17_local.py --stage recovery %*
exit /b %errorlevel%

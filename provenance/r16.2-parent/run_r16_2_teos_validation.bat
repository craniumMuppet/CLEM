@echo off
setlocal
cd /d "%~dp0"
python -c "import gsw" >nul 2>&1
if errorlevel 1 (
  echo R16.2 TEOS-10 validation dependency is missing.
  echo Run: python -m pip install -r requirements-r16-teos10.txt
  exit /b 2
)
python verify_r16_local.py --validation-only %*
exit /b %errorlevel%

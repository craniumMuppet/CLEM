@echo off
setlocal
cd /d "%~dp0"
python -c "import gsw" >nul 2>&1
if errorlevel 1 (
  echo R17 matched TEOS-10 validation requires gsw.
  echo Installing the pinned R16/R17 TEOS dependency...
  python -m pip install -r requirements-r17-teos10.txt
  if errorlevel 1 exit /b %errorlevel%
)
python verify_r17_local.py --stage teos %*
exit /b %errorlevel%

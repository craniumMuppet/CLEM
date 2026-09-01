@echo off
setlocal
cd /d "%~dp0"
python -c "import gsw" >nul 2>&1
if errorlevel 1 (
  echo R17 all-stage validation includes matched TEOS-10 experiments and requires gsw.
  echo Installing the pinned R16/R17 TEOS dependency...
  python -m pip install -r requirements-r17-teos10.txt
  if errorlevel 1 exit /b %errorlevel%
)
python verify_r17_local.py --stage all %*
exit /b %errorlevel%

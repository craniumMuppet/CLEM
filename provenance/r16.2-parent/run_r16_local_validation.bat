@echo off
setlocal
cd /d "%~dp0"
echo R16.1 hotfix: the 31 completed R16 non-TEOS experiments do not need to be rerun.
echo Running only the three previously blocked TEOS-10 experiments.
call run_r16_1_teos_validation.bat %*
exit /b %errorlevel%

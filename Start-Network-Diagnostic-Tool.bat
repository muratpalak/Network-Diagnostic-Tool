@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m netdiag.dashboard %*
) else (
  python -m netdiag.dashboard %*
)
if errorlevel 1 (
  echo Python 3.10+ is required or the application could not start.
  pause
  exit /b 1
)
endlocal

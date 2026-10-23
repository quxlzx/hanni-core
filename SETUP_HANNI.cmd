@echo off
setlocal
cd /d "%~dp0"
echo.
echo Starting H.A.N.N.I. setup...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_hanni.ps1"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo H.A.N.N.I. setup failed with exit code %EXITCODE%.
  echo Review the error above, then press any key to close.
  pause >nul
  exit /b %EXITCODE%
)
echo.
echo Setup finished successfully.
echo Use START_HANNI.cmd to launch the dashboard and configured assistant model.
pause

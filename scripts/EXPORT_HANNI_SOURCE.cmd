@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\export_source.ps1"
if errorlevel 1 (
  echo.
  echo H.A.N.N.I. source export failed.
  pause
  exit /b 1
)
echo.
echo Source ZIP is ready in the parent folder.
pause

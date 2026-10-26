@echo off
setlocal
if not exist "%~dp0scripts\setup_hanni.ps1" goto missing_repository
if not exist "%~dp0pyproject.toml" goto missing_repository
if not exist "%~dp0src\hanni\__init__.py" goto missing_repository
cd /d "%~dp0"
echo.
echo Starting H.A.N.N.I. setup...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_hanni.ps1" %*
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
echo See the launch and Windows startup status above. START_HANNI.cmd also opens the assistant.
pause
exit /b 0

:missing_repository
echo.
echo HANNI setup needs the complete extracted repository.
echo Windows may have opened this file from inside the downloaded ZIP.
echo.
echo 1. Close this window and return to the downloaded ZIP in File Explorer.
echo 2. Right-click the ZIP and choose Extract All.
echo 3. Extract to a permanent folder, for example C:\HANNI.
echo 4. Open the extracted folder and run SETUP_HANNI.cmd there.
echo.
echo Keep the scripts and src folders beside SETUP_HANNI.cmd.
echo If you already extracted everything, download a fresh ZIP and extract it again.
echo Press any key to close.
pause >nul
exit /b 2

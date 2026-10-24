@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_desktop.ps1" %*
if errorlevel 1 (
    echo HANNI OS could not start. Run SETUP_HANNI.cmd or scripts\build_desktop.ps1.
    pause
    exit /b 1
)

@echo off
setlocal
if exist "%~dp0..\START_BRAIN.cmd" (
    call "%~dp0..\START_BRAIN.cmd" %*
    exit /b
)
title HANNI stick
cd /d "%~dp0"
echo Starting HANNI from this stick... first boot benches the models and
echo takes 2-3 minutes. Keep this window open while HANNI is running.
echo.
py -3.12 firstboot.py --serve --wait --ui --port 8311
if errorlevel 1 (
    echo.
    echo HANNI failed to start. Review the error above and the service logs.
    pause
)

@echo off
title HANNI stick
cd /d %~dp0
echo Starting HANNI from this stick... first boot benches the models and
echo takes 2-3 minutes. Keep this window open while HANNI is running.
echo.
py -3.12 firstboot.py --serve --wait --port 8311 2>nul
if errorlevel 9009 py -3 firstboot.py --serve --wait --port 8311
if errorlevel 9009 python firstboot.py --serve --wait --port 8311
if errorlevel 1 (
    echo.
    echo HANNI failed to start. Screenshot this window and send it to Laynce.
    pause
)

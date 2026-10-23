@echo off
title HANNI brain
cd /d %~dp0
echo Starting the HANNI native brain from this repo... first run benches
echo the models and takes 2-3 minutes. Keep this window open while it runs.
echo (Need models first?  py scripts\get_models.py)
echo.
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python scripts\firstboot.py --serve --wait --ui --port 8311
) else (
    py -3.12 scripts\firstboot.py --serve --wait --ui --port 8311 2>nul
    if errorlevel 9009 py -3 scripts\firstboot.py --serve --wait --ui --port 8311
    if errorlevel 9009 python scripts\firstboot.py --serve --wait --ui --port 8311
)
if errorlevel 1 (
    echo.
    echo HANNI failed to start. Screenshot this window for the error above.
    pause
)

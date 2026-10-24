@echo off
setlocal
title HANNI brain
cd /d "%~dp0"
echo.
echo  Choose HANNI's model:
echo    [1] Auto   - benchmark and pick the best this machine can host
echo    [2] 2B     - MiniCPM5-2B     (light, fast, small machines)
echo    [3] 3.7B   - K2 Horizon 3.7B (balanced)
echo    [4] 7B     - K2 Horizon 7B   (needs a real GPU or 16GB+ RAM)
echo.
choice /c 1234 /n /m "Pick 1-4: "
if errorlevel 4 set TIER=7b
if errorlevel 3 set TIER=3.7b
if errorlevel 2 set TIER=2b
if errorlevel 1 set TIER=auto
echo.
echo Starting the HANNI native brain (%TIER% tier)... first run benches
echo the models and takes 2-3 minutes. Keep this window open while it runs.
echo (Need models first?  py scripts\get_models.py)
echo.
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"
    if errorlevel 1 (
        echo Hanni OS requires Python 3.12+. Rebuild .venv with SETUP_HANNI.cmd.
        pause
        exit /b 1
    )
    .venv\Scripts\python scripts\firstboot.py --serve --wait --ui --port 8311 --tier %TIER% %*
) else (
    py -3.12 scripts\firstboot.py --serve --wait --ui --port 8311 --tier %TIER% %*
)
set "LAUNCH_EXIT=%ERRORLEVEL%"
if not "%LAUNCH_EXIT%"=="0" (
    echo.
    echo HANNI failed to start. Screenshot this window for the error above.
    pause
    exit /b %LAUNCH_EXIT%
) else (
    echo.
    echo HANNI stopped. You can close this window.
)

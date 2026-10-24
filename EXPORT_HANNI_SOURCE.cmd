@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\export_source.ps1" %*
exit /b %ERRORLEVEL%

@echo off
cd /d %~dp0
python firstboot.py --serve
if errorlevel 1 pause

@echo off
rem Compatibility entry point: use the same native stack and ports as START_BRAIN.
call "%~dp0START_BRAIN.cmd" %*
exit /b %ERRORLEVEL%

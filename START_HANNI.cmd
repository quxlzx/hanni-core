@echo off
rem Open the Windows application; its agent runs in the background.
call "%~dp0START_HANNI_OS.cmd" %*
exit /b %ERRORLEVEL%

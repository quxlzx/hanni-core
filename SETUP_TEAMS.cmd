@echo off
echo This setup trusts HANNI's localhost development certificate for your Windows account.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_teams.ps1" -TrustLocalCertificate
if errorlevel 1 pause

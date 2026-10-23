# HANNI test-cage setup (run once as Administrator in PowerShell)
# Turns a fresh Windows box into an always-on HANNI test cage.
# Usage:  Set-ExecutionPolicy Bypass -Scope Process -Force; .\setup_test_cage.ps1 -SshPublicKey "ssh-ed25519 AAAA..."

param([string]$SshPublicKey = "")

Write-Host "== power: never sleep on AC =="
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 15
powercfg /change hibernate-timeout-ac 0

Write-Host "== OpenSSH server =="
if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {
    Get-WindowsCapability -Online -Name "OpenSSH.Server*" | Add-WindowsCapability -Online
}
Set-Service sshd -StartupType Automatic
Start-Service sshd

if ($SshPublicKey) {
    $keyPath = "C:\ProgramData\ssh\administrators_authorized_keys"
    New-Item -ItemType Directory -Force (Split-Path $keyPath) | Out-Null
    Add-Content -Path $keyPath -Value $SshPublicKey
    icacls $keyPath /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
    Write-Host "SSH key installed for administrators."
}

Write-Host "== toolchain via winget =="
winget install -e --id Microsoft.VCRedist.2015+.x64 --source winget --accept-package-agreements --accept-source-agreements --silent
winget install -e --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements --silent
winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements

Write-Host "== done. reboot recommended, then: =="
Write-Host "  git clone <repo> C:\cage\HANNI ; cd C:\cage\HANNI"
Write-Host "  py -3.12 -m venv .venv ; .venv\Scripts\pip install -e \".[dev]\""
Write-Host "  .venv\Scripts\python scripts\get_models.py --tier 2b"
Write-Host "  .venv\Scripts\python -m pytest tests -q --ignore tests\integration"

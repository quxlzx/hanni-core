[CmdletBinding()]
param([switch]$TrustLocalCertificate, [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run SETUP_HANNI.cmd first.' }
Push-Location $repoRoot
try {
    if (-not $SkipInstall) {
        & $python -m pip install -e '.[teams]'
        if ($LASTEXITCODE -ne 0) { throw 'Teams setup dependencies could not be installed.' }
        & npm.cmd ci --prefix frontend
        if ($LASTEXITCODE -ne 0) { throw 'Teams frontend dependencies could not be installed.' }
        & npm.cmd run build --prefix frontend
        if ($LASTEXITCODE -ne 0) { throw 'Teams frontend could not be built.' }
    }
    & $python scripts/build_teams.py
    if ($LASTEXITCODE -ne 0) { throw 'Teams package could not be built.' }
    if ($TrustLocalCertificate) {
        # Trust only this development leaf, for the current Windows user.
        # No CA signing key, machine-wide trust, admin elevation or firewall rule.
        $certificate = Join-Path $repoRoot 'state\teams\tls\localhost.pem'
        & certutil.exe -user -addstore Root $certificate
        if ($LASTEXITCODE -ne 0) { throw 'Local certificate trust failed. See docs/MICROSOFT_TEAMS.md.' }
    }
    Write-Host 'Upload dist\teams\HANNI-Teams.zip in Teams: Apps > Manage your apps > Upload an app.'
    Write-Host 'Then run START_TEAMS.cmd and enter its pairing code in the HANNI tab.'
} finally { Pop-Location }

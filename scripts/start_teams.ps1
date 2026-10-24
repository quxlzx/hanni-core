[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$certificate = Join-Path $repoRoot 'state\teams\tls\localhost.pem'
$privateKey = Join-Path $repoRoot 'state\teams\tls\localhost.key'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run SETUP_HANNI.cmd first.' }
if ((-not (Test-Path -LiteralPath $certificate)) -or (-not (Test-Path -LiteralPath $privateKey))) {
    throw 'Run SETUP_TEAMS.cmd first to build the app package and trust its local development certificate.'
}
Write-Host 'HANNI must be running on this PC. START_HANNI.cmd can keep it in the tray.'
Write-Host 'This launcher hosts the Teams tab only. It does not start or stop your agent.'
Push-Location $repoRoot
try {
    & $python -m hanni.teams.server --cert $certificate --key $privateKey
    if ($LASTEXITCODE -ne 0) { throw 'Teams launcher failed. Check the message above.' }
} finally { Pop-Location }

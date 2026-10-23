[CmdletBinding()]
param([string]$ConfigFile = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$repoRoot = Get-HanniRepoRoot
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall
if (-not $ConfigFile) { $ConfigFile = Join-Path $repoRoot 'data\hermes\config.json' }
if (-not (Test-Path -LiteralPath $ConfigFile)) { throw 'Configure the private Hermes bridge before starting its SSH forwards.' }
Write-Host 'HANNI starts these forwards automatically and stops its own tunnel on backend exit.'
Write-Host 'Standalone use: keep this window open; Ctrl+C stops this script. Occupied ports are left untouched.'
& $python -m hanni.hermes.tunnel --config $ConfigFile
exit $LASTEXITCODE

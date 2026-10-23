[CmdletBinding()]
param([switch]$CheckLive)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$python = Initialize-HanniEnvironment -RepoRoot (Get-HanniRepoRoot) -SkipInstall
& $python -m hanni.tools.google_auth status
if ($LASTEXITCODE -ne 0) { throw 'Google account status failed.' }
if ($CheckLive) {
    & $python -m hanni.cli tool-run gmail.search --arg account=all --arg limit=2 --json
    if ($LASTEXITCODE -ne 0) { throw 'Email read failed or returned a partial result.' }
    & $python -m hanni.cli tool-run google_calendar.next --arg account=all --json
    if ($LASTEXITCODE -ne 0) { throw 'Calendar read failed or returned a partial result.' }
}

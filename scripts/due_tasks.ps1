[CmdletBinding()]
param([ValidateRange(1,366)][int]$Days = 7)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$python = Initialize-HanniEnvironment -RepoRoot (Get-HanniRepoRoot) -SkipInstall
& $python -m hanni.cli tool-run todo.due --arg "days=$Days" --json
if ($LASTEXITCODE -ne 0) { throw 'Task query failed.' }

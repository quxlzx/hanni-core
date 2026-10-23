<#
.SYNOPSIS
    H.A.N.N.I.: set up the local environment and run the foundation health check.
.DESCRIPTION
    Creates .venv if needed, installs the package in editable mode, then runs `hanni health`.
    Milestone 1 keeps llama.cpp in a separate terminal via scripts/start_llama.ps1.
.PARAMETER SkipInstall
    Skip pip install (faster when nothing changed).
.PARAMETER Json
    Print the health report as JSON.
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$Json
)

. (Join-Path $PSScriptRoot "_common.ps1")
$repoRoot = Get-HanniRepoRoot
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall:$SkipInstall

$healthArgs = @("-m", "hanni.cli", "health")
if ($Json) { $healthArgs += "--json" }
& $python @healthArgs
exit $LASTEXITCODE

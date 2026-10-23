<#
.SYNOPSIS
    Start a configured H.A.N.N.I. llama.cpp model on loopback.
.DESCRIPTION
    Uses model metadata from config/models.yaml. Supports single-GPU and
    multi-GPU llama.cpp launches. Multi-GPU profiles can identify the intended
    adapters by name, which prevents an integrated GPU from accidentally joining
    a split intended for discrete cards.
.PARAMETER ModelId
    Configured model id; defaults to supervisor.
.PARAMETER SkipInstall
    Skip reinstalling the editable H.A.N.N.I. package.
#>
[CmdletBinding()]
param(
    [string]$ModelId = "supervisor",
    [switch]$SkipInstall
)

. (Join-Path $PSScriptRoot "_common.ps1")
$repoRoot = Get-HanniRepoRoot
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall:$SkipInstall

# Shared Python builder probes this installed llama.cpp build and resolves GPU names.
& $python -m hanni.models.serve --model-id $ModelId
exit $LASTEXITCODE

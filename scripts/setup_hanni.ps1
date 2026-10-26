<#
.SYNOPSIS
    One-time setup for the current single-model HANNI assistant checkpoint.
.DESCRIPTION
    Creates/refreshes .venv, installs HANNI with speech dependencies,
    ensures llama.cpp is available when possible, validates the shipped configuration,
    exercises read-only local tools. Use -RunTests for the automated test suite.
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$RunTests,
    [switch]$SkipLlamaInstall,
    [switch]$SkipDesktop,
    [switch]$ForceRecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$repoRoot = Get-HanniRepoRoot
Set-Location $repoRoot

$venvPath = Join-Path $repoRoot '.venv'
if ($ForceRecreateVenv -and (Test-Path $venvPath)) {
    Remove-Item -Path $venvPath -Recurse -Force
}
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall

Write-Host 'Installing/updating HANNI + speech dependencies ...'
& $python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
& $python -m pip install -e '.[speech]'
if ($LASTEXITCODE -ne 0) { throw 'HANNI dependency installation failed' }

Write-Host 'Preparing app-local llama.cpp (CPU and Vulkan; no WinGet install required) ...'
$runtimeArguments = @('scripts\prepare_llama_runtime.py', '--verify')
if ($SkipLlamaInstall) { $runtimeArguments += '--offline' }
& $python @runtimeArguments
if ($LASTEXITCODE -ne 0) { throw 'The bundled inference runtime could not be prepared. Check the connection or populate the verified offline cache first.' }

Write-Host 'Validating HANNI configuration ...'
& $python -m hanni.cli health --no-file-log
if ($LASTEXITCODE -ne 0) { throw 'HANNI health check failed' }
& $python -m hanni.cli model-info --no-file-log
if ($LASTEXITCODE -ne 0) { throw 'Model configuration check failed' }
& $python -m hanni.cli tools --no-file-log
if ($LASTEXITCODE -ne 0) { throw 'Tool registry check failed' }
& $python -m hanni.cli tool-run system.stats --args '{}' --no-file-log
if ($LASTEXITCODE -ne 0) { throw 'Read-only system tool smoke test failed' }
& $python -m hanni.cli speech-info --no-file-log
if ($LASTEXITCODE -ne 0) { throw 'Speech configuration check failed' }

if ($RunTests -and -not $SkipTests) {
    Write-Host 'Running automated tests ...'
    & $python -m pip install -e '.[dev]' --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Development dependency installation failed' }
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed' }
}

if (-not $SkipDesktop) {
    Write-Host 'Building the Windows application and installing shortcuts ...'
    & (Join-Path $PSScriptRoot 'build_desktop.ps1') -SkipFrontend -OfflineLlamaRuntime:$SkipLlamaInstall
}

Write-Host ''
Write-Host 'HANNI setup complete.' -ForegroundColor Green
Write-Host 'llama.cpp: included locally (CPU + Vulkan)'
Write-Host 'Open HANNI OS from the Desktop or Start menu, or run START_HANNI.cmd.'
Write-Host 'For Google, run .\.venv\Scripts\hanni.exe google login from this folder.'

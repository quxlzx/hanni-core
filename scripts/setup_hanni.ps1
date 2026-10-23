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

function Find-LlamaServer {
    $cmd = Get-Command llama-server -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $winGetBase = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe'
    $candidate = Join-Path $winGetBase 'llama-server.exe'
    if (Test-Path $candidate) { return $candidate }
    return $null
}

$llamaServer = Find-LlamaServer
if (-not $llamaServer -and -not $SkipLlamaInstall -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host 'llama.cpp not found. Installing with WinGet ...'
    & winget install --id ggml.llamacpp --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "WinGet could not install llama.cpp (exit code $LASTEXITCODE)." }
    $llamaServer = Find-LlamaServer
}

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

Write-Host ''
Write-Host 'HANNI setup complete.' -ForegroundColor Green
if ($llamaServer) { Write-Host "llama.cpp: ready ($llamaServer)" }
else { Write-Host 'llama.cpp: not detected; install it before first model start.' -ForegroundColor Yellow }
Write-Host 'Use START_HANNI.cmd to launch the dashboard + assistant.'
Write-Host 'For Google, run .\.venv\Scripts\hanni.exe google login from this folder.'

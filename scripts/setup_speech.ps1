<#
.SYNOPSIS
    Install the optional local speech stack for H.A.N.N.I. Milestone 2.
.DESCRIPTION
    Installs sounddevice, faster-whisper, Silero VAD, ONNX Runtime, and their
    dependencies into H.A.N.N.I.'s existing .venv. Nothing is sent to a cloud
    inference service; model files may download once on first use.
.PARAMETER SkipTests
    Do not run the automated test suite after installation.
#>
[CmdletBinding()]
param(
    [switch]$SkipTests
)

. (Join-Path $PSScriptRoot "_common.ps1")
$repoRoot = Get-HanniRepoRoot
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall

Write-Host "Installing H.A.N.N.I. speech + dev dependencies ..."
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -e ".[dev,speech]"
if ($LASTEXITCODE -ne 0) { throw "speech dependency installation failed" }

Write-Host ""
Write-Host "Speech configuration:"
& $python -m hanni.cli speech-info --no-file-log
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "Running automated tests ..."
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Speech stack installed. Next: .\scripts\test_m2.ps1 -SkipInstall"

<#
.SYNOPSIS
    Start the current H.A.N.N.I. single-PC assistant with one command.
.DESCRIPTION
    Ensures the local environment exists, starts the configured llama.cpp
    Supervisor if one is not already healthy, waits for it to become ready,
    and then starts H.A.N.N.I.'s always-listening attention loop.

    When this script started llama.cpp itself, it stops that model process tree
    when H.A.N.N.I. exits. An already-running model server is left alone.
.PARAMETER ShowIgnored
    Show ignored transcripts for relevance debugging.
.PARAMETER Device
    Optional microphone device index or name.
.PARAMETER KeepModelRunning
    Leave a llama.cpp instance started by this launcher running after H.A.N.N.I. exits.
.PARAMETER ModelReadyTimeoutSeconds
    Maximum time to wait for llama.cpp to become healthy. Defaults to 900 seconds
    because the first start can include a multi-GB model download.
#>
[CmdletBinding()]
param(
    [switch]$ShowIgnored,
    [string]$Device,
    [switch]$KeepModelRunning,
    [ValidateRange(30, 3600)]
    [int]$ModelReadyTimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "_common.ps1")
$repoRoot = Get-HanniRepoRoot
Set-Location $repoRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "           STARTING H.A.N.N.I." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$needsSetup = -not (Test-Path $pythonPath)
if (-not $needsSetup) {
    & $pythonPath -c "import hanni" 2>$null
    $needsSetup = ($LASTEXITCODE -ne 0)
}

if ($needsSetup) {
    Write-Host "H.A.N.N.I. is not set up in this folder yet. Running automatic setup ..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "setup_hanni.ps1") -SkipTests
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

# Foundation health first so failures are clear before model/microphone startup.
& $python -m hanni.cli health --no-file-log | Out-Host
if ($LASTEXITCODE -ne 0) { throw "H.A.N.N.I. foundation health check failed." }

function Test-ModelHealthy {
    & $python -m hanni.cli model-health --no-file-log *> $null
    return ($LASTEXITCODE -eq 0)
}

$startedModelProcess = $null
if (Test-ModelHealthy) {
    Write-Host "Supervisor model is already running and healthy."
}
else {
    Write-Host "Supervisor model is not running. Starting llama.cpp ..."
    $startLlama = Join-Path $PSScriptRoot "start_llama.ps1"
    $argumentList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$startLlama`"",
        "-SkipInstall"
    )

    # A separate minimized PowerShell owns llama.cpp. This keeps the main window
    # available for H.A.N.N.I.'s conversation output while still showing a model
    # console if the user restores it for diagnostics.
    $startedModelProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentList -WindowStyle Minimized -PassThru

    Write-Host "Waiting for the Supervisor to become ready."
    Write-Host "The first launch can take several minutes while the model downloads."
    $deadline = (Get-Date).AddSeconds($ModelReadyTimeoutSeconds)
    $lastProgress = Get-Date
    while (-not (Test-ModelHealthy)) {
        if ($startedModelProcess.HasExited) {
            throw "llama.cpp exited before the Supervisor became healthy. Restore/check its PowerShell window for the error."
        }
        if ((Get-Date) -ge $deadline) {
            throw "Timed out after $ModelReadyTimeoutSeconds seconds waiting for the Supervisor model."
        }
        if (((Get-Date) - $lastProgress).TotalSeconds -ge 10) {
            $remaining = [Math]::Max(0, [int](($deadline - (Get-Date)).TotalSeconds))
            Write-Host "  Still loading... (timeout in ${remaining}s)"
            $lastProgress = Get-Date
        }
        Start-Sleep -Seconds 2
    }
    Write-Host "Supervisor is ready." -ForegroundColor Green
}

$attendArgs = @("-m", "hanni.cli", "attend")
if ($ShowIgnored) { $attendArgs += "--show-ignored" }
if ($Device) {
    $attendArgs += "--device"
    $attendArgs += $Device
}

Write-Host ""
Write-Host "H.A.N.N.I. is now listening." -ForegroundColor Green
Write-Host "Say 'Hanni' to activate. Use a configured disengage phrase to return to standby."
Write-Host "Press Ctrl+C to stop H.A.N.N.I. completely."
Write-Host ""

try {
    & $python @attendArgs
    exit $LASTEXITCODE
}
finally {
    if ($startedModelProcess -and -not $KeepModelRunning) {
        Write-Host ""
        Write-Host "Stopping the llama.cpp process started by this launcher ..."
        try {
            # /T terminates descendants as well, including llama-server.exe.
            & taskkill.exe /PID $startedModelProcess.Id /T /F *> $null
        }
        catch {
            Write-Warning "Could not stop the llama.cpp process tree automatically: $($_.Exception.Message)"
        }
    }
}

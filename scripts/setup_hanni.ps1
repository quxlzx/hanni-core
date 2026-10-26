<#
.SYNOPSIS
    One-time setup for the current single-model HANNI assistant checkpoint.
.DESCRIPTION
    Creates/refreshes .venv, installs HANNI with speech dependencies,
    prepares and verifies llama.cpp and a model, validates the shipped configuration,
    launches the assistant and registers sign-in startup. Use -RunTests for the automated test suite.
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$RunTests,
    [switch]$SkipLlamaInstall,
    [switch]$SkipDesktop,
    [switch]$NoStartup,
    [switch]$NoLaunch,
    [switch]$Offline,
    [switch]$ForceRecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$repoRoot = Get-HanniRepoRoot
Set-Location $repoRoot
$setupLogFolder = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HANNI OS'
New-Item -ItemType Directory -Path $setupLogFolder -Force | Out-Null
$setupLog = Join-Path $setupLogFolder 'setup.log'
Start-Transcript -Path $setupLog -Append | Out-Null
Write-Host "Setup log: $setupLog"

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
if ($SkipLlamaInstall -or $Offline) { $runtimeArguments += '--offline' }
& $python @runtimeArguments
if ($LASTEXITCODE -ne 0) { throw 'The bundled inference runtime could not be prepared. Check the connection or populate the verified offline cache first.' }

Write-Host 'Preparing the configured model for automatic launch ...'
$modelArguments = @('scripts\configure_local_install.py')
if ($Offline) { $modelArguments += '--offline' }
& $python @modelArguments
if ($LASTEXITCODE -ne 0) { throw 'The configured model is not ready. Setup did not register a broken startup entry.' }

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
    $desktopExecutable = Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe'
    $openDesktop = @(Get-CimInstance Win32_Process -Filter "Name = 'HANNI OS.exe'" | Where-Object { $_.ExecutablePath -eq $desktopExecutable })
    if ($openDesktop.Count -eq 0) {
        Write-Host 'Building the Windows application and installing shortcuts ...'
        & (Join-Path $PSScriptRoot 'build_desktop.ps1') -SkipFrontend -NoShortcuts -OfflineLlamaRuntime:($SkipLlamaInstall -or $Offline)
    } else {
        Write-Host 'The existing desktop is open. Its runtime and model have been repaired; the executable will be rebuilt on a later setup when it is closed.'
    }
    if (-not $NoLaunch) {
        if ($openDesktop.Count -gt 0) {
            & $python 'scripts\configure_local_install.py' --repair-open-desktop
            if ($LASTEXITCODE -ne 0) { throw 'The repaired assistant did not start. See the startup error above.' }
        }
        & (Join-Path $PSScriptRoot 'start_desktop.ps1')
        & $python 'scripts\configure_local_install.py' --wait-ready
        if ($LASTEXITCODE -ne 0) { throw 'The assistant is not ready. Setup did not register a new startup entry.' }
        Write-Host 'HANNI OS and its configured assistant are running.'
    }
    & (Join-Path $PSScriptRoot 'install_desktop_shortcuts.ps1') -Startup:(-not $NoStartup)
}

Write-Host ''
Write-Host 'HANNI setup complete.' -ForegroundColor Green
Write-Host 'llama.cpp: included locally (CPU + Vulkan)'
Write-Host 'Open HANNI OS from the Desktop or Start menu, or run START_HANNI.cmd.'
Write-Host 'For Google, run .\.venv\Scripts\hanni.exe google login from this folder.'
Stop-Transcript | Out-Null

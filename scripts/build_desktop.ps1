[CmdletBinding()]
param([switch]$SkipInstall, [switch]$SkipFrontend, [switch]$NoShortcuts, [switch]$OfflineLlamaRuntime,
      [string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$distributionPath = if ($OutputDirectory) {
    if ([System.IO.Path]::IsPathRooted($OutputDirectory)) { [System.IO.Path]::GetFullPath($OutputDirectory) }
    else { [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory)) }
} else { Join-Path $repoRoot 'dist' }
if ($distributionPath -eq $repoRoot -or $distributionPath -eq [System.IO.Path]::GetPathRoot($distributionPath)) {
    throw 'Choose a dedicated desktop build output directory.'
}
if ($OutputDirectory -and -not $NoShortcuts) { throw 'Custom output builds require -NoShortcuts; installed shortcuts target dist\HANNI OS.' }
$releaseExecutable = Join-Path $distributionPath 'HANNI OS\HANNI OS.exe'
$runningClient = @(Get-CimInstance Win32_Process -Filter "Name = 'HANNI OS.exe'" |
    Where-Object { $_.ExecutablePath -eq $releaseExecutable })
if ($runningClient.Count -gt 0) {
    throw 'Close HANNI OS desktop before rebuilding its portable directory. Its separate assistant session can stay running.'
}
$backendPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$nativePython = Join-Path $repoRoot 'build\desktop-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $nativePython)) {
    if (-not (Test-Path -LiteralPath $backendPython)) { throw 'Run HANNI setup first so .venv exists.' }
    & $backendPython -m venv (Join-Path $repoRoot 'build\desktop-venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated desktop build environment.' }
}
Push-Location $repoRoot
try {
    Write-Host 'Preparing the pinned CPU and Vulkan inference runtimes ...'
    $runtimeArguments = @('scripts\prepare_llama_runtime.py', '--verify')
    if ($OfflineLlamaRuntime) { $runtimeArguments += '--offline' }
    & $nativePython @runtimeArguments
    if ($LASTEXITCODE -ne 0) { throw 'Bundled llama.cpp preparation failed. No desktop release was built.' }
    if (-not $SkipInstall) {
        & $nativePython -m pip install -r 'desktop\requirements.txt'
        if ($LASTEXITCODE -ne 0) { throw 'Desktop dependency installation failed.' }
    }
    if (-not $SkipFrontend) {
        & npm.cmd run build --prefix frontend
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    & $nativePython 'desktop\create_icon.py'
    if ($LASTEXITCODE -ne 0) { throw 'Native icon build failed.' }
    & $nativePython -m PyInstaller --noconfirm --distpath $distributionPath --workpath 'build\desktop-package' 'desktop\HANNI OS.spec'
    if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
    $releaseRuntime = Join-Path $distributionPath 'HANNI OS\_internal\runtimes\llama.cpp'
    $releaseArchive = Join-Path $distributionPath 'HANNI-OS-Windows-x64.zip'
    & $nativePython 'scripts\prepare_llama_runtime.py' --destination $releaseRuntime --check-only --verify --archive $releaseArchive
    if ($LASTEXITCODE -ne 0) { throw 'Packaged inference engine or release archive verification failed.' }
    Write-Host "Shareable application archive: $releaseArchive"
    Write-Host "Built $releaseExecutable"
    if (-not $NoShortcuts) {
        & (Join-Path $PSScriptRoot 'install_desktop_shortcuts.ps1')
    }
} finally { Pop-Location }

[CmdletBinding()]
param([switch]$SkipInstall, [switch]$SkipFrontend, [switch]$NoShortcuts)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$releaseExecutable = Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe'
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
    & $nativePython -m PyInstaller --noconfirm --distpath 'dist' --workpath 'build\desktop-package' 'desktop\HANNI OS.spec'
    if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
    Write-Host "Built $(Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe')"
    if (-not $NoShortcuts) {
        & (Join-Path $PSScriptRoot 'install_desktop_shortcuts.ps1')
    }
} finally { Pop-Location }

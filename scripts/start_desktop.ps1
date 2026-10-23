[CmdletBinding()]
param([string]$Url = 'http://127.0.0.1:8765', [switch]$AttachOnly, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$launchArgs = @('--url', $Url, '--repo-root', $repoRoot)
if ($AttachOnly) { $launchArgs += '--attach-only' }
$executable = Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe'
if ((-not $Dev) -and (Test-Path -LiteralPath $executable)) {
    & $executable @launchArgs
} else {
    $nativePython = Join-Path $repoRoot 'build\desktop-venv\Scripts\pythonw.exe'
    if (-not (Test-Path -LiteralPath $nativePython)) { throw 'Run scripts\build_desktop.ps1 first to install native desktop dependencies.' }
    & $nativePython (Join-Path $repoRoot 'desktop\main.py') @launchArgs
}

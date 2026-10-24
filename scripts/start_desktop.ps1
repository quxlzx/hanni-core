[CmdletBinding()]
param([string]$Url = 'http://127.0.0.1:8311', [switch]$AttachOnly, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$launchArgs = @('--url', $Url, '--repo-root', $repoRoot)
if ($AttachOnly) { $launchArgs += '--attach-only' }
$executable = Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe'
if ((-not $Dev) -and (Test-Path -LiteralPath $executable)) {
    $program = $executable
} else {
    $nativePython = Join-Path $repoRoot 'build\desktop-venv\Scripts\pythonw.exe'
    if (-not (Test-Path -LiteralPath $nativePython)) {
        & (Join-Path $PSScriptRoot 'build_desktop.ps1') -SkipFrontend
        if (-not (Test-Path -LiteralPath $executable)) { throw 'Desktop setup failed. Run scripts\build_desktop.ps1 to see the build error.' }
        $program = $executable
    } else {
        $program = $nativePython
        $launchArgs = @((Join-Path $repoRoot 'desktop\main.py')) + $launchArgs
    }
}
# Start-Process joins ArgumentList on Windows PowerShell; quote each argument
# using Windows command-line rules so repository paths containing spaces work.
$quoted = foreach ($argument in $launchArgs) {
    '"' + [regex]::Replace([regex]::Replace($argument, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
Start-Process -FilePath $program -ArgumentList ($quoted -join ' ') -WorkingDirectory $repoRoot -WindowStyle Normal

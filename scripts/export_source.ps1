[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputPath) { $OutputPath = Join-Path (Split-Path $repoRoot -Parent) 'HANNI_SOURCE_FOR_REVIEW.zip' }
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $command = Get-Command py -ErrorAction SilentlyContinue
    if (-not $command) { $command = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $command) { throw 'Python 3.12+ is needed to export source.' }
    $python = $command.Source
}
& $python (Join-Path $PSScriptRoot 'export_source.py') --output $OutputPath
if ($LASTEXITCODE -ne 0) { throw 'Source export failed. An existing output is never overwritten; choose a new filename.' }

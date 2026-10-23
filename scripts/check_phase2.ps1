[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$phase2Root = Split-Path -Parent $PSScriptRoot
$phase2Python = Join-Path $phase2Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $phase2Python)) { throw 'Use the existing Hanni environment; this script installs nothing.' }
$phase2Tests = @('tests/unit/test_phase2_intent.py')
$phase2Tests += @(Get-ChildItem -LiteralPath (Join-Path $phase2Root 'tests/unit') -Filter 'test_workflow*.py' | ForEach-Object { $_.FullName })
$phase2Tests += @('tests/unit/test_dashboard_workflows.py', 'tests/unit/test_phase1_response.py', 'tests/unit/test_tools.py', 'tests/safety')
Push-Location $phase2Root
try {
    & $phase2Python -m pytest @phase2Tests -o 'addopts=' -q --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'Phase 2 regression checks failed.' }
} finally { Pop-Location }

[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$phase3Root = Split-Path -Parent $PSScriptRoot
$phase3Python = Join-Path $phase3Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $phase3Python)) { throw 'Use the existing HANNI environment; installs nothing.' }
Push-Location $phase3Root
try {
    & $phase3Python -m pytest tests/unit/test_phase3_contract_context.py tests/unit/test_adaptive_model_routing.py tests/unit/test_compute_registry.py tests/unit/test_memory_context_v35.py tests/unit/test_project_context.py -o 'addopts=' -q --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'Phase 3 checks failed.' }
} finally { Pop-Location }

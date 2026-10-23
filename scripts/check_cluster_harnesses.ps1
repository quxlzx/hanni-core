[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$harnessRoot=Split-Path -Parent $PSScriptRoot
$harnessPython=Join-Path $harnessRoot '.venv\Scripts\python.exe'
Push-Location $harnessRoot
try {
    & $harnessPython -m pytest tests/unit/test_cluster_harnesses.py tests/unit/test_cluster_worker_checks.py tests/unit/test_dashboard_workflows.py tests/unit/test_cluster_harness_graph.py tests/unit/test_phase3_contract_context.py tests/unit/test_compute_registry.py tests/unit/test_tools.py tests/safety -o addopts= -q --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'Cluster harness regression failed.' }
} finally { Pop-Location }

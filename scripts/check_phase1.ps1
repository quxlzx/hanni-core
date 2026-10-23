[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$phase1Root = Split-Path -Parent $PSScriptRoot
$phase1Python = Join-Path $phase1Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $phase1Python)) { throw 'Use the existing Hanni Python environment; this check installs nothing.' }
$phase1Tests = @(
    'tests/unit/test_phase1_response.py', 'tests/unit/test_orchestrator.py',
    'tests/unit/test_model_client.py', 'tests/unit/test_attention.py',
    'tests/unit/test_barge_in.py', 'tests/unit/test_tools.py',
    'tests/unit/test_reliability_execution.py', 'tests/unit/test_mcp.py',
    'tests/unit/test_mcp_session.py', 'tests/unit/test_campaign1_routing_regressions.py',
    'tests/unit/test_voice_interruption.py', 'tests/unit/test_desktop_voice.py',
    'tests/unit/test_speech_pipeline.py', 'tests/unit/test_speech_buffer.py', 'tests/safety',
    'tests/unit/test_mcp_hub_registry.py', 'tests/unit/test_mcp_hub_api.py',
    'tests/unit/test_mcp_hub.py', 'tests/unit/test_workflow_readback_routing.py',
    'tests/unit/test_workflow_registry_guard.py', 'tests/unit/test_workflow_planner.py'
)
Push-Location $phase1Root
try {
    & $phase1Python -m pytest @phase1Tests -o 'addopts=' -q --tb=short
    if ($LASTEXITCODE -ne 0) { throw 'Phase 1 regression checks failed.' }
} finally { Pop-Location }

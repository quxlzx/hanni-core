"""Future registry growth cannot silently outrun evaluation coverage."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from hanni.evals.llm_tools import load_scenarios
from hanni.evals.regression_policy import new_capability_gaps
from hanni.evals.routing import build_default_host, load_cases
ROOT = Path(__file__).resolve().parents[2]
FROZEN_V1_NAMES_SHA256 = 'c2b448cf6d9d9f8340352df79404d171b578b757987cf68479b9c1d1a284e400'

def test_new_registered_capabilities_need_routing_and_llm_coverage():
    snapshot = json.loads((ROOT / 'evals/routing/capability_snapshot.json').read_text(encoding='utf-8'))
    baseline = sorted((row['name'] for row in snapshot['capabilities']))
    digest = hashlib.sha256(json.dumps(baseline, separators=(',', ':')).encode()).hexdigest()
    assert len(baseline) == 150 and digest == FROZEN_V1_NAMES_SHA256
    host = build_default_host(config_dir=ROOT / 'config')
    names = [definition.name for definition in host.registry.definitions()]
    routing = load_cases(ROOT / 'evals/routing/cases.jsonl')
    llm = load_scenarios(ROOT / 'evals/llm_tools/cases.jsonl')
    gaps = new_capability_gaps(names, baseline, routing, llm)
    assert not gaps, f'New capabilities need at least two routing probes and two LLM scenarios: {gaps}'

def test_policy_does_not_count_mock_menu_presence_as_llm_coverage():
    probe = SimpleNamespace(primary='future.status', required=(), blocked_capabilities=())
    gaps = new_capability_gaps(['future.status'], [], [probe, probe], [{'results': {'future.status': {}}}, {'required_tools': ['future.status']}])
    assert gaps == {'future.status': {'routing_probes': 2, 'llm_scenarios': 1}}

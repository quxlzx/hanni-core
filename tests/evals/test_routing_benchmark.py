from collections import Counter
from pathlib import Path
from hanni.config.loader import load_config
from hanni.evals.routing import evaluate_case, load_cases, run_benchmark
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from tests.helpers import REPO_ROOT, write_config_dir
CASES = REPO_ROOT / 'evals' / 'routing' / 'cases.jsonl'
EXPECTED_COUNTS = {'diagnostics': 250, 'calendar_read': 90, 'calendar_create': 70, 'files': 60, 'process_system': 55, 'hanni_model': 40, 'date_time': 40, 'ambiguous': 40, 'blocked_writes': 40, 'mixed_domain': 35, 'slang_typos': 30}

def _host(tmp_path: Path) -> McpHost:
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    mcp = config.hanni.mcp
    return McpHost(registry, read_only=mcp.read_only, max_tools=mcp.max_tools_per_turn, allowed_actions=mcp.allowed_actions)

def test_routing_corpus_preserves_750_original_cases_and_expands_registry_coverage():
    cases = load_cases(CASES)
    assert len(cases) >= 1050
    assert len({case.id for case in cases}) == len(cases)
    original = [c for c in cases if not c.id.startswith(('REGISTRY-', 'HARDENING-', 'GOOGLE-LAYER-'))]
    assert len({case.query for case in original}) == 750
    assert Counter((case.family for case in original)) == EXPECTED_COUNTS

def test_every_named_capability_in_corpus_exists_in_frozen_registry(tmp_path):
    host = _host(tmp_path)
    registered = {definition.name for definition in host.registry.definitions()}
    for case in load_cases(CASES):
        referenced = set(case.required) | set(case.acceptable) | set(case.forbidden) | set(case.blocked_capabilities)
        for group in case.required_any:
            referenced.update(group)
        referenced.update(case.fixed_arguments)
        referenced.update(case.fixed_argument_prefixes)
        missing = referenced - registered
        assert not missing, f'{case.id} references missing capabilities: {sorted(missing)}'

def test_benchmark_never_executes_capability_handlers(tmp_path, monkeypatch):
    host = _host(tmp_path)

    def forbidden_execute(*args, **kwargs):
        raise AssertionError('routing eval must never execute a capability')
    monkeypatch.setattr(host.registry, 'execute', forbidden_execute)
    report = run_benchmark(host, load_cases(CASES))
    assert report.total >= 1050
    assert report.coverage['missing'] == []
    assert all((0.0 <= row.score <= 100.0 for row in report.results))

def test_frozen_tomorrow_case_resolves_before_model(tmp_path):
    host = _host(tmp_path)
    case = next((case for case in load_cases(CASES) if case.id == 'CALENDAR-READ-011'))
    result = evaluate_case(host, case)
    assert result.selected[0] == 'google_calendar.agenda'
    assert result.argument_score == 20.0

def test_explicit_non_calendar_write_is_blocked(tmp_path):
    host = _host(tmp_path)
    case = next((case for case in load_cases(CASES) if case.id == 'BLOCKED-WRITES-001'))
    result = evaluate_case(host, case)
    assert result.selected == ()
    assert result.safety_score == 20.0

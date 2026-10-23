"""Benchmark/checker contracts; controlled fixtures are never live model scores."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx
import pytest
from scripts.campaign5_benchmark.author import FAMILIES, build, seal
from scripts.campaign5_benchmark.checkers import equal, grade, parse_json, validate_code
from scripts.campaign5_benchmark.runner import capture_http, run_case, summary, reported_metadata, request_limits

def test_prospective_corpus_has_exact_family_denominators_and_no_model_facing_oracles(tmp_path):
    inputs, oracles = build(tmp_path)
    assert Counter((c['category'] for c in inputs['cases'])) == {key: 20 for key in FAMILIES}
    assert len({c['id'] for c in inputs['cases']}) == 200
    assert {c['id'] for c in inputs['cases']} == {o['id'] for o in oracles['oracles']}
    assert all((not set(c) & {'expected', 'oracle', 'checker_inputs'} for c in inputs['cases']))
    assert all((c['request']['task_category'] == FAMILIES[c['category']] for c in inputs['cases']))
    assert all((c['limits']['temperature'] == 0 and c['limits']['top_p'] == 1 for c in inputs['cases']))
    from hanni.config import load_config
    from hanni.tools.registry import build_default_registry
    registry = build_default_registry(load_config(data_dir=tmp_path / 'independent-registry'))
    for oracle in oracles['oracles']:
        if oracle['checker_id'] == 'tool_selection':
            expected = oracle['expected']
            registry.get(expected['capability']).validate_arguments(expected['arguments'])

def test_seal_is_immutable_and_reproducible(tmp_path):
    path = tmp_path / 'sealed.json'
    original = {'cases': [{'id': 'prospective'}]}
    digest = seal(path, original)
    assert seal(path, deepcopy(original)) == digest
    before = path.read_bytes()
    with pytest.raises(RuntimeError):
        seal(path, {'cases': [{'id': 'altered'}]})
    assert path.read_bytes() == before

@pytest.mark.parametrize('text', ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '```json\n{}\n```'])
def test_structural_checker_rejects_invalid_json(text):
    verdict = grade(text, {'checker_id': 'json_exact', 'expected': {'x': 2}})
    assert verdict['passed'] is False

def test_json_types_and_missing_measurements_are_not_equated():
    assert not equal({'available': 1}, {'available': True})
    assert not equal({'percent': 0}, {'percent': None})
    assert not equal({'id': 9}, {'id': '009'})
    assert not equal({'value': 3, 'extra': 'claim'}, {'value': 3})

def test_graph_checker_accepts_two_topological_orders_but_rejects_dependency_and_duration_errors():
    oracle = {'checker_id': 'dag', 'checker_inputs': {'graph': {'A': [], 'B': [], 'C': ['A', 'B']}, 'durations': {'A': 2, 'B': 4, 'C': 3}}}
    for order in (['A', 'B', 'C'], ['B', 'A', 'C']):
        assert grade(json.dumps({'status': 'ready', 'order': order, 'earliest_finish': {'A': 2, 'B': 4, 'C': 7}}), oracle)['passed']
    assert not grade(json.dumps({'status': 'ready', 'order': ['C', 'A', 'B'], 'earliest_finish': {'A': 2, 'B': 4, 'C': 7}}), oracle)['passed']
    assert not grade(json.dumps({'status': 'ready', 'order': ['A', 'B', 'C'], 'earliest_finish': {'A': 2, 'B': 4, 'C': 5}}), oracle)['passed']
    cyclic = {'checker_id': 'dag', 'checker_inputs': {'graph': {'A': ['B'], 'B': ['A']}, 'durations': {'A': 1, 'B': 1}}}
    assert grade('{"status":"impossible"}', cyclic)['passed']

@pytest.mark.parametrize('code', ['import os\ndef solve(value): return 0', 'def solve(value): return open("private.txt").read()', 'def solve(value): return value.__class__', 'def solve(value): return solve(value)', 'def solve(value):\n while True: pass', 'def solve(value): return eval(value)', 'def solve(value): return 10 ** 1000000'])
def test_coding_security_boundary_rejects_imports_io_reflection_recursion_and_unbounded_constructs(code):
    with pytest.raises(ValueError):
        validate_code(code)

def test_actual_disposable_coding_child_checks_independent_cases_and_wrong_algorithm():
    oracle = {'checker_id': 'python_function', 'checker_inputs': {'tests': [{'input': [2, -5, 8], 'expected': 5}, {'input': [], 'expected': 0}, {'input': [9], 'expected': 9}]}}
    correct = grade('def solve(value):\n return sum(value)', oracle)
    wrong = grade('def solve(value):\n return len(value)', oracle)
    assert correct['passed'] and correct['child_exit_code'] == 0
    assert not wrong['passed'] and wrong['observed'] == [3, 0, 1]

def test_original_httpx_wire_observer_retains_exact_bytes_without_auth_headers():
    raw = b'{"model":"controlled-fixture","choices":[{"message":{"content":"actual fixture bytes"}}]}'
    seen = []

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            seen.append(body)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with capture_http({('http', '127.0.0.1', server.server_port)}) as records:
            with httpx.Client(trust_env=False) as client:
                response = client.post(f'http://127.0.0.1:{server.server_port}/v1/chat/completions', json={'messages': [{'role': 'user', 'content': 'synthetic'}]}, headers={'Authorization': 'Bearer controlled-header-canary'})
                assert response.content == raw
        assert len(records) == 1 and records[0]['raw_response'].encode() == raw
        assert records[0]['request_body'].encode() == seen[0]
        assert 'controlled-header-canary' not in json.dumps(records)
        assert records[0]['status'] == 200 and records[0]['latency_ms'] is not None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)

def test_execution_boundary_rejects_oracle_and_reference_backed_final_before_engine_use():
    case = {'request': {'privacy_categories': ['synthetic']}, 'expected': {'answer': 42}}
    with pytest.raises(ValueError, match='Oracle'):
        run_case(case, None, mode='pinned', endpoint_id='local:fixture')
    with pytest.raises(ValueError, match='Reference-backed'):
        run_case(case, None, mode='selective', collaboration_verifier=lambda text: True)

def test_blocked_tasks_keep_null_semantics_and_no_inference_latency():
    rows = [{'classification': 'BLOCKED_NO_INFERENCE', 'semantic_pass': None, 'real_generation_dispatches': 0, 'total_request_ms': 12} for _ in range(20)]
    value = summary(rows)
    assert value['tasks'] == 20 and value['semantic_measured'] == 0 and (value['semantic_passed'] == 0)
    assert value['blocked_or_unmeasured'] == 20 and value['latency_ms'] == {'n': 0, 'p50': None, 'p95': None}

def test_shared_public_case_shape_does_not_serialize_checker_answers(tmp_path):
    inputs, oracles = build(tmp_path)
    case = next((c for c in inputs['cases'] if c['category'] == 'coding'))
    assert 'tests' not in json.dumps(case)
    assert any((o['id'] == case['id'] and o['checker_inputs']['tests'] for o in oracles['oracles']))

def test_reported_sse_alias_and_finish_flags_do_not_become_weight_identity():
    text = 'data: {"model":"alias-only","choices":[{"delta":{"content":"x"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\ndata: [DONE]\n'
    fields = reported_metadata(text)
    assert fields['reported_model_aliases'] == ['alias-only'] and fields['finish_reasons'] == ['length']
    assert 'weights' not in fields and 'runtime/weights proof remains separate' in fields['identity_scope']

def test_declined_collaboration_has_no_fabricated_response_object():

    class ControlledCollaboration:

        def run(self, *args, **kwargs):
            return {'state': 'failed', 'selected_output': None, 'participants': []}

    class ControlledEngine:
        compute = None
        collaboration = ControlledCollaboration()

        def _inventory(self):
            return []

        def snapshot(self):
            return {'endpoints': [], 'decisions': []}
    case = {'id': 'controlled-no-output', 'category': 'planning', 'request': {'privacy_categories': ['synthetic'], 'output_tokens': 256}, 'messages': [{'role': 'user', 'content': 'synthetic'}]}
    row = run_case(case, ControlledEngine(), mode='selective')
    assert row['classification'] == 'COLLABORATION_DECLINED_NO_INFERENCE'
    assert row['actual_response'] is None and row['semantic_pass'] is None
    assert row['real_generation_dispatches'] == 0 and row['raw_http'] == []

def test_frozen_profiles_use_fresh_case_db_and_preserve_latency_between_cases(tmp_path):
    from hanni.config import load_config
    from hanni.models.adaptive import AdaptiveModelEngine
    from scripts.campaign5_benchmark.live import final_case_engine
    config = load_config(data_dir=tmp_path / 'arm')
    arm = AdaptiveModelEngine(config, data_dir=tmp_path / 'arm')
    checkpoint = tmp_path / 'checkpoint.sqlite3'
    with __import__('sqlite3').connect(checkpoint) as backup:
        arm._connect().backup(backup)
    before = checkpoint.read_bytes()
    try:
        for index in range(2):
            root = tmp_path / f'case-{index}'
            with final_case_engine(arm, root, config, checkpoint.resolve()) as engine:
                assert engine._connect().execute('SELECT COUNT(*) FROM measurements').fetchone()[0] == 0
                engine._connect().execute('INSERT INTO measurements VALUES(?,?,?,?,?)', ('controlled-latency', 'local:fixture', 'identity', 'analysis', json.dumps({'latency_ms': 999})))
                engine._connect().commit()
        assert checkpoint.read_bytes() == before
        assert arm._connect().execute('SELECT COUNT(*) FROM measurements').fetchone()[0] == 0
    finally:
        arm.close()

def test_native_request_metadata_is_not_forwarded_as_generation_kwargs():
    from hanni.models.adaptive import ModelSelectionError
    captured = {}

    class ControlledEngine:
        compute = None

        def _inventory(self):
            return []

        def snapshot(self):
            return {'endpoints': [], 'decisions': []}

        def execute(self, *args, **kwargs):
            captured.update(kwargs)
            raise ModelSelectionError('Controlled unavailable endpoint.')
    case = {'id': 'metadata-control', 'category': 'planning', 'request': {'privacy_categories': ['synthetic'], 'output_tokens': 256}, 'messages': [{'role': 'user', 'content': 'synthetic'}], 'limits': {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'max_fallbacks': 0, 'timeout_seconds': 120}}
    row = run_case(case, ControlledEngine(), mode='adaptive')
    assert captured['max_fallbacks'] == 0 and 'timeout_seconds' not in captured
    assert captured['max_tokens'] == 256 and row['generation_settings'] == {'max_tokens': 256, 'temperature': 0, 'top_p': 1}
    assert row['requested_deadline_seconds'] == 120 and row['classification'] == 'BLOCKED_NO_INFERENCE'
    assert row['semantic_pass'] is None

@pytest.mark.parametrize('limits', [{'max_tokens': True, 'temperature': 0, 'top_p': 1}, {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'max_fallbacks': True}, {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'timeout_seconds': float('nan')}, {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'timeout_seconds': 0}, {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'unknown_control': 1}])
def test_prospective_request_limits_reject_unknown_nonfinite_and_boolean_controls(limits):
    with pytest.raises(ValueError):
        request_limits({'request': {'output_tokens': 256}, 'limits': limits})

def test_deadline_uses_original_cancellation_without_poisoning_caller_event():
    import time
    from hanni.models.adaptive import ModelSelectionError
    parent = threading.Event()

    class ControlledEngine:
        compute = None

        def _inventory(self):
            return []

        def snapshot(self):
            return {'endpoints': [], 'decisions': []}

        def execute(self, *args, **kwargs):
            deadline = time.monotonic() + 1
            while not kwargs['cancellation'].is_set() and time.monotonic() < deadline:
                time.sleep(0.001)
            assert kwargs['cancellation'].is_set()
            raise ModelSelectionError('Controlled cancelled admission.')
    case = {'id': 'deadline-control', 'category': 'planning', 'request': {'privacy_categories': ['synthetic'], 'output_tokens': 256}, 'messages': [{'role': 'user', 'content': 'synthetic'}], 'limits': {'max_tokens': 256, 'temperature': 0, 'top_p': 1, 'timeout_seconds': 0.005}}
    row = run_case(case, ControlledEngine(), mode='pinned', endpoint_id='local:controlled', cancellation=parent)
    assert row['classification'] == 'CANCELLED_NO_INFERENCE' and (not parent.is_set())

def test_generation_request_budget_reserves_fallbacks_and_all_collaboration_rounds():
    from types import SimpleNamespace
    from scripts.campaign5_benchmark.live import request_reservation
    engine = SimpleNamespace(_settings=lambda: {'max_fallbacks': 2}, collaboration=SimpleNamespace(limits=SimpleNamespace(max_participants=3, max_rounds=2)))
    case = {'request': {'output_tokens': 256}, 'limits': {'max_tokens': 256, 'temperature': 0, 'top_p': 1}}
    assert request_reservation(engine, 'pinned', case) == 1
    assert request_reservation(engine, 'adaptive', case) == 3
    assert request_reservation(engine, 'selective', case) == 6
    bounded = deepcopy(case)
    bounded['limits']['max_fallbacks'] = 0
    assert request_reservation(engine, 'adaptive', bounded) == 1
    bounded['limits']['max_fallbacks'] = 3
    with pytest.raises(ValueError):
        request_reservation(engine, 'adaptive', bounded)

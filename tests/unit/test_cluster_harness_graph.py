"""Actual optional LangGraph, controlled specialist/model seams (not live)."""
import importlib.util
from pathlib import Path
import pytest
pytest.importorskip('langgraph.graph')

def worker():
    path = Path(__file__).resolve().parents[2] / 'deployment/cluster-harnesses/worker.py'
    spec = importlib.util.spec_from_file_location('hanni_sandbox_worker_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_real_graph_sequences_each_specialist_then_checks_and_review():
    module = worker()
    visited = []

    def stage(state, role):
        visited.append(role)
        return {'stages': state['stages'] + [{'role': role, 'advisory': True}]}

    def checks(state):
        visited.append('checks')
        return {'checks': [{'exit_code': 0}]}

    def review(state):
        assert state['checks'] == [{'exit_code': 0}]
        visited.append('review')
        return {'notes': [{'advisory': True}]}
    module.run_stage = stage
    module.checks = checks
    module.review = review
    result = module.build_graph().invoke({'task': {}, 'notes': [], 'stages': [], 'checks': []}, config={'recursion_limit': 8})
    assert visited == ['manager', 'researcher', 'coder', 'editor', 'checks', 'review']
    assert 'task_complete' not in result

def test_real_graph_does_not_continue_after_provider_failure():
    module = worker()
    visited = []

    def stage(state, role):
        visited.append(role)
        if role == 'researcher':
            raise RuntimeError('Provider unavailable')
        return {}
    module.run_stage = stage
    with pytest.raises(RuntimeError, match='unavailable'):
        module.build_graph().invoke({'task': {}, 'notes': [], 'stages': [], 'checks': []}, config={'recursion_limit': 8})
    assert visited == ['manager', 'researcher']

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from hanni.evals.model_lab import corpus
from hanni.evals import routing
from scripts.campaign8_ui.lab_controls import cases, install_delay

def test_model_free_pagination_inputs_are_supported_and_answers_separate():
    inputs, oracles = cases()
    assert len(corpus('routing-development')) >= 101
    assert {r['id'] for r in inputs} == {r['id'] for r in oracles}
    assert all((not set(r) & {'oracle', 'expected', 'check'} for r in inputs))
    assert all(('Send message' not in [s.get('name') for s in r['steps']] for r in inputs))
    assert next((s for s in inputs[0]['steps'] if s.get('selector') == 'input[aria-label="Cases"]'))['value'] == '101'

def test_timing_leaf_preserves_original_result_and_has_finite_budget():
    case = routing.RoutingCase.from_dict(corpus('routing-development')[0])
    sentinel = object()
    backend = SimpleNamespace()
    with patch.object(routing, 'evaluate_case', return_value=sentinel) as original, patch('scripts.campaign8_ui.lab_controls.time.sleep') as sleep, ExitStack() as stack:
        install_delay(backend, stack)
        for _ in range(204):
            assert routing.evaluate_case(None, case) is sentinel
        with pytest.raises(RuntimeError, match='budget'):
            routing.evaluate_case(None, case)
        assert original.call_count == sleep.call_count == 204
        assert all((r['delay_seconds'] == 0.15 for r in backend.lab_control_calls))
    assert len(backend.lab_control_calls) == 204

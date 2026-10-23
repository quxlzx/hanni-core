"""Original authenticated HTTP admission, using disposable stores and no inference."""
from urllib.parse import urlencode
import pytest
from scripts.campaign8_ui.backend import original_backend

@pytest.fixture(scope='module')
def backend(tmp_path_factory):
    with original_backend(tmp_path_factory.mktemp('c8-preflight') / 'runtime') as instance:
        yield instance
    assert instance.closed and (not instance.thread.is_alive())

def path(**changes):
    fields = {'suite_id': 'routing-development', 'endpoint_id': '', 'max_cases': '2', 'max_tokens': '32'} | changes
    return '/api/model-lab/preflight?' + urlencode(fields)

def test_model_free_http_admission_matches_original_direct_admission(backend):
    direct = backend.server.model_lab.preflight('routing-development', None, 2, 32)
    status, actual = backend.request(path())
    assert status == 200 and actual == direct and (actual['eligible'] is True)
    assert backend.server.model_lab.snapshot()['runs'] == []
    assert backend.ready()['model_generation'] is False

def test_blank_endpoint_does_not_admit_a_model_required_suite(backend):
    status, actual = backend.request(path(suite_id='structured-development', max_cases='1'))
    assert status == 200 and actual['eligible'] is False
    assert backend.server.model_lab.snapshot()['runs'] == []

def test_named_endpoint_remains_ineligible_for_model_free_suite(backend):
    status, actual = backend.request(path(endpoint_id='local:supervisor'))
    assert status == 200 and actual['eligible'] is False

@pytest.mark.parametrize('changes', [{'max_cases': ''}, {'max_cases': '0'}, {'max_cases': '1.5'}, {'max_tokens': ''}, {'max_tokens': '31'}, {'max_tokens': '1025'}, {'suite_id': ''}, {'suite_id': 'unsupported-synthetic-suite'}, {'extra': 'unsupported'}])
def test_invalid_original_preflight_fields_still_rejected(backend, changes):
    status, _ = backend.request(path(**changes))
    assert status == 400
    assert backend.server.model_lab.snapshot()['runs'] == []

def test_missing_endpoint_key_remains_invalid(backend):
    status, _ = backend.request('/api/model-lab/preflight?suite_id=routing-development&max_cases=2&max_tokens=32')
    assert status == 400

def test_private_token_gate_still_precedes_preflight(backend):
    status, _ = backend.request(path(), authorized=False)
    assert status == 403
    assert backend.server.model_lab.snapshot()['runs'] == []

def test_other_private_routes_retain_blank_field_behavior(backend):
    status, blank = backend.request('/api/model-lab?limit=')
    omitted_status, omitted = backend.request('/api/model-lab')
    assert status == omitted_status == 200
    for key in ('history_limit', 'history_offset', 'runs', 'total_runs'):
        assert blank[key] == omitted[key]

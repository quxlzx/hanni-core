"""Prospective guard contracts; no live model, health or network requests."""
from copy import deepcopy
import json
from unittest.mock import patch
import pytest
from scripts.campaign9_tools.live import MAX_POSTS, MAX_CASE_POSTS, ProbeAdmissionError, WireResponse, public_cases, validate_wire

def payload():
    return {'model': 'supervisor', 'messages': [{'role': 'user', 'content': 'Synthetic fixed prompt'}], 'max_tokens': 128, 'temperature': 0}

def admitted(body=None, **changes):
    arguments = {'prompt': 'Synthetic fixed prompt', 'global_count': 0, 'case_count': 0}
    arguments.update(changes)
    return validate_wire('http://127.0.0.1:8080/v1/chat/completions', 'POST', body or payload(), **arguments)

@pytest.mark.parametrize('url', ['http://127.0.0.1:8081/v1/chat/completions', 'http://' + '.'.join(('10', '42', '0', '31')) + ':8080/v1/chat/completions', 'https://fixture.invalid/v1/chat/completions', 'https://example.invalid/127.0.0.1:8080/v1/chat/completions', 'http://localhost:8080/v1/chat/completions', 'http://127.0.0.1:8080/start'])
def test_actual_transport_scope_cannot_expand(url):
    with pytest.raises(ProbeAdmissionError):
        validate_wire(url, 'POST', payload(), prompt='Synthetic fixed prompt', global_count=0, case_count=0)

@pytest.mark.parametrize('change', [{'global_count': MAX_POSTS}, {'case_count': MAX_CASE_POSTS}])
def test_fixed_post_limits_do_not_admit_replays(change):
    with pytest.raises(ProbeAdmissionError):
        admitted(**change)

@pytest.mark.parametrize('field,value', [('max_tokens', 129), ('temperature', 0.1), ('messages', [{'role': 'user', 'content': 'Unsealed prompt'}]), ('messages', ['not a message'])])
def test_unsealed_payload_is_refused(field, value):
    body = payload()
    body[field] = value
    with pytest.raises(ProbeAdmissionError):
        admitted(body)

def test_real_original_request_shape_and_readonly_health_remain_supported():
    assert admitted()
    assert validate_wire('http://127.0.0.1:8080/health', 'GET', None, prompt='fixed', global_count=MAX_POSTS, case_count=MAX_CASE_POSTS) is False

def test_prospective_authoring_contacts_no_endpoint_or_process():
    with patch('socket.socket.connect', side_effect=AssertionError('network')), patch('subprocess.Popen', side_effect=AssertionError('process')):
        cases = public_cases()
    assert len(cases) == 4
    assert len({case['id'] for case in cases}) == 4
    assert all(('expected' not in case and 'answer' not in case for case in cases))

def test_wire_observer_preserves_original_response_values():
    import io
    original = io.BytesIO(b'actual synthetic response bytes')
    record = {'response_bytes': 0, '_raw': bytearray(), 'truncated': False}
    observer = WireResponse(original, record)
    assert observer.read() == b'actual synthetic response bytes'
    assert bytes(record['_raw']) == b'actual synthetic response bytes'

@pytest.mark.parametrize('positional,timeout', [(True, 0.4), (True, 9), (False, 0.4), (False, 9)])
def test_metadata_timeout_forwarding_preserves_original_native_signature(positional, timeout):
    import urllib.request
    from types import SimpleNamespace
    from scripts.campaign9_tools.live import guarded_transport
    observed = []

    def original_contract(opener, request, data=None, timeout=3):
        observed.append({'data': data, 'timeout': timeout})
        return object()
    state = SimpleNamespace(prompt='Synthetic fixed prompt', case_posts=0)
    with patch.object(urllib.request.OpenerDirector, 'open', original_contract):
        with guarded_transport(state, [], [], {'process': {}}, admission=lambda value: None):
            opener = urllib.request.OpenerDirector()
            request = urllib.request.Request('http://127.0.0.1:8080/health')
            if positional:
                opener.open(request, None, timeout)
            else:
                opener.open(request, timeout=timeout)
    assert observed == [{'data': None, 'timeout': min(timeout, 3)}]
    assert state.case_posts == 0

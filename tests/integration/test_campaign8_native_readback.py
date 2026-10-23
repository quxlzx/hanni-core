"""Bounded Settings readback authority; no native window or HTTP requests."""
from types import SimpleNamespace
import pytest
from scripts.campaign8_native.development import authenticated_readback

class Requests:

    def __init__(self, *, token='synthetic-session-authority'):
        self.token = token
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        data = {'token': self.token} if url.endswith('/api/chat') else {'available': True, 'devices': [], 'nested': {'token': 'withheld', 'password': 'withheld', 'name': 'Default'}}
        return SimpleNamespace(status=200, json=lambda: data)

def session(requests):
    return SimpleNamespace(url='http://127.0.0.1:61731', page=SimpleNamespace(request=requests))

@pytest.mark.parametrize('path', ['/api/audio-devices', '/api/gpu-routing'])
def test_exact_settings_readback_uses_original_token_and_scrubs_secrets(path):
    requests = Requests()
    result = authenticated_readback(session(requests), path)
    assert result['status'] == 200 and result['data']['devices'] == []
    assert result['data']['nested'] == {'name': 'Default'}
    assert requests.calls == [('http://127.0.0.1:61731/api/chat', {}), ('http://127.0.0.1:61731' + path, {'headers': {'X-Hanni-Token': 'synthetic-session-authority', 'Origin': 'http://127.0.0.1:61731'}})]

@pytest.mark.parametrize('path', ['/api/audio-devices/private', '/api/gpu-routing/private', '/api/shutdown', 'https://example.invalid/api/audio-devices', None])
def test_new_readback_scope_does_not_admit_children_or_unapproved_routes(path):
    requests = Requests()
    with pytest.raises(ValueError):
        authenticated_readback(session(requests), path)
    assert requests.calls == []

def test_missing_original_token_rejects_settings_readback_before_dispatch():
    requests = Requests(token=None)
    with pytest.raises(RuntimeError):
        authenticated_readback(session(requests), '/api/audio-devices')
    assert len(requests.calls) == 1

"""Actual Hermes client/control/store against an owned loopback service."""
import json
import threading
from uuid import uuid4

import pytest

from hanni.hermes.client import BridgeUnavailable, Client
from hanni.hermes.state import Conflict


def test_background_completion_reaches_owning_conversation_and_is_not_duplicated(harness, monkeypatch):
    h = harness
    conversation = h.service.hub.create_conversation(str(uuid4()))
    request = str(uuid4())
    result = h.invoke('/hermes Inspect only the synthetic report', conversation=conversation, key=request)
    assert result['ok'], result
    task = h.bridge.store.submission(request)
    h.bridge.store.event(task['id'], 'Controlled investigation ended.', state='review_required',
                         result={'model_claims': 'Unverified prose is not a successful tool receipt.'})
    import hanni.dashboard.chat as chat_module
    monkeypatch.setattr(chat_module, '_hub', h.service.hub)
    h.control.monitor = threading.Thread(target=h.control.watch, daemon=True)
    h.control.monitor.start()
    h.control.stop.step_and_wait()
    rows = h.service.hub.snapshot(conversation=conversation)['messages']
    completions = [r for r in rows if r['channel'] == 'hermes']
    assert len(completions) == 1, 'Background result was delivered to a different conversation or lost.'
    assert completions[0]['turn'] == task['id']
    assert 'Unverified prose' not in completions[0]['content']
    assert not [r for r in h.service.hub.snapshot(conversation='default')['messages'] if r['channel'] == 'hermes']
    h.control.stop.step_and_wait()
    assert len([r for r in h.service.hub.snapshot(conversation=conversation)['messages'] if r['channel'] == 'hermes']) == 1


def test_cancellation_before_submission_reaches_real_control_without_remote_job(harness):
    h = harness
    cancel = threading.Event()
    cancel.set()
    before = len(h.bridge.store.list())
    with pytest.raises(RuntimeError, match='cancel'):
        h.service.work.dispatch('hermes', 'Do not start this job', 'default', str(uuid4()), cancel)
    assert len(h.bridge.store.list()) == before


def test_reconnect_same_request_recovers_acknowledgment_without_duplicate_job(harness):
    h = harness
    request = str(uuid4())
    first = h.invoke('/hermes Inspect only synthetic input', key=request)
    assert first['ok']
    before = len(h.bridge.store.list())
    again = h.invoke('/hermes Inspect only synthetic input', key=request)
    assert first == again and len(h.bridge.store.list()) == before
    with pytest.raises(ValueError, match='already used'):
        h.invoke('/hermes A changed task', key=request)


@pytest.mark.parametrize('body', [[], None, 42, 'not an object'])
def test_malformed_bridge_top_level_response_is_a_protocol_error(harness, monkeypatch, body):
    client = harness.control.client
    original = harness.bridge.dispatch
    monkeypatch.setattr(harness.bridge, 'dispatch', lambda method, path, request: body if path == '/health' else original(method, path, request))
    with pytest.raises(BridgeUnavailable, match='response|protocol'):
        client.request('GET', '/health')


def test_missing_authentication_reference_is_honest_unavailability_not_path_exception(harness):
    path = harness.control.client.config['token_file']
    from pathlib import Path
    Path(path).unlink()
    with pytest.raises(BridgeUnavailable, match='authentication|credential'):
        harness.control.client.request('GET', '/health')

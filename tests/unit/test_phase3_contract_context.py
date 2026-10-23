"""Contract/context boundaries; fixture planners/providers are not live inference."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from hanni.models.endpoint_contract import build, validate, ContractError
from hanni.memory.grounded import GroundedPersonalContext
from hanni.memory.retrieval import ContextAwareRetriever
from hanni.memory.store import MemoryStore
from tests.unit.test_adaptive_model_routing import engine, prove, request

def frame():
    return build(endpoint_id='nex', model_id='nex', loaded_model_id='nex', binding={'model': 'nex'}, configured_context=32768, status='healthy', sampled_at=1000, advertised=('chat',))

def test_shared_contract_source_is_identical():
    root = Path(__file__).resolve().parents[2]
    peer = root / 'data/control-center-import/backend/endpoint_contract.py'
    if not peer.exists():
        peer = root / 'phase3_evidence/control-center/endpoint_contract.py'
    if not peer.exists():
        pytest.skip('Separate Control Center source is unavailable; cross-project byte identity NOT TESTED.')
    assert (root / 'src/hanni/models/endpoint_contract.py').read_bytes() == peer.read_bytes()

def test_cancelled_relay_drain_timeout_does_not_mask_cancel_or_leak_tracking(monkeypatch):
    import subprocess
    from hanni.compute.registry import ComputeError
    from hanni.compute.transport import InferenceTransport
    checks = []

    def check_source():
        checks.append(True)
        if len(checks) > 1:
            raise ComputeError('cancelled')

    class Process:
        killed = False

        def poll(self):
            return None

        def kill(self):
            self.killed = True

        def communicate(self, *args, **kwargs):
            raise subprocess.TimeoutExpired('owned helper', 1)
    process = Process()
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **kw: process)
    transport = InferenceTransport(object(), relay_only=True)
    monkeypatch.setattr(transport, '_ssh', lambda *a: ['ssh'])
    monkeypatch.setattr(transport, '_address', lambda *a: 'authorized')
    with pytest.raises(ComputeError, match='cancelled'):
        transport._relay_request({'worker_id': 'test', 'remote_port': 8080}, {}, 'GET', '/health', None, 3, None, check_source)
    assert process.killed
    assert transport.clients == {}

def test_healthy_is_not_verified_capability_or_capacity():
    value = frame()
    assert validate(value, now=1000)['health_fresh']
    assert not any((f['verified'] for f in value['features'].values()))
    assert value['context']['measured_usable'] is None
    assert not validate(value, now=1011)['health_fresh']
    assert not validate(value, now=999)['health_fresh']

@pytest.mark.parametrize('mutation', [lambda f: f.update(loaded_model_id='other'), lambda f: f['auth_reference'].update(secret='bad'), lambda f: f['features']['chat'].update(verified=True), lambda f: f['context'].update(measured_usable=32768), lambda f: f['resources'].update(available=True)])
def test_unproven_or_credential_contracts_fail(mutation):
    value = frame()
    mutation(value)
    with pytest.raises(ContractError):
        validate(value, now=1000)

def test_opt_in_does_not_route_simple_or_private_context_remotely(engine):
    prove(engine, 'local:supervisor', ('text',))
    prove(engine, 'worker:fixture', ('text',))
    engine.configure(policy='measured_work')
    assert engine.select(request())['endpoint']['local']
    selection = engine.select(request(task_category='planning', complexity='complex'))
    assert any(('stronger_role_not_measured' in r['reasons'] for r in selection['excluded']))
    engine.configure(policy='resident_first')
    assert engine.select(request(task_category='planning', complexity='complex'))['endpoint']['local']
    engine.configure(policy='balanced')
    assert engine.snapshot()['policy'] == 'balanced'

def test_recall_provenance_correction_deletion_and_irrelevance(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('my preferred code editor is Code', source_ref='owner-turn:1')
    store.remember('my favorite drink is tea')
    context = GroundedPersonalContext(ContextAwareRetriever(store))
    package = json.loads(context.retrieve('preferred editor').text)
    assert [m['id'] for m in package['memories']] == [record.id]
    assert package['memories'][0]['context_kind'] == 'explicit_owner_fact'
    assert package['memories'][0]['source_ref'] == 'owner-turn:1'
    assert package['memories'][0]['current_state_verified'] is False
    store.correct(record.id, 'my preferred code editor is Vim', expected_updated_at=record.updated_at.isoformat())
    assert 'Vim' in context.retrieve('editor').text and 'Code' not in context.retrieve('editor').text
    store.delete(record.id)
    assert not context.retrieve('editor').text

def test_stale_observations_and_credentials_are_excluded(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    context = GroundedPersonalContext(ContextAwareRetriever(store), clock=lambda: 1000)
    context.set_ephemeral(observations=[{'source': 'system.stats', 'subject': 'CPU', 'verification': 'VERIFIED', 'sampled_at': 939, 'data': {'cpu_percent': 20}}])
    assert not context.retrieve('CPU').text
    context.set_ephemeral(observations=[{'source': 'system.stats', 'subject': 'CPU', 'verification': 'VERIFIED', 'sampled_at': 1000, 'data': {'cpu_percent': 20}}])
    package = json.loads(context.retrieve('CPU').text)
    assert package['live_observations'][0]['context_kind'] == 'live_observation'
    context.set_ephemeral(conversation=[{'role': 'user', 'content': 'CPU password is hunter2'}])
    assert not context.retrieve('CPU').text

def test_temporary_context_never_becomes_a_durable_fact(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    context = GroundedPersonalContext(ContextAwareRetriever(store))
    before = store.fingerprint()
    context.set_ephemeral(conversation=[{'role': 'user', 'content': 'The Orion project discussion is temporary.'}])
    package = json.loads(context.retrieve('Orion project').text)
    assert package['temporary_conversation'][0]['durable'] is False
    assert store.fingerprint() == before
    assert len(context.retrieve('Orion').text.encode()) <= 4000

def test_small_existing_budget_does_not_break_context_startup(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    store.remember('my preferred editor is Vim')
    context = GroundedPersonalContext(ContextAwareRetriever(store), max_bytes=128)
    assert context.retrieve('editor').text == ''

def test_owner_fact_recall_crosses_voice_and_keyboard_without_model_or_tools(tmp_path):
    from hanni.memory.session import MemoryAwareSession

    class NoInference:

        def stream_response(self, *a, **kw):
            raise AssertionError('Unnecessary inference/tool discovery')
    store = MemoryStore(tmp_path / 'memory.db')
    voice = MemoryAwareSession(NoInference(), store, source='voice')
    ''.join(voice.stream_response('Remember my preferred code editor is Vim.'))
    keyboard = MemoryAwareSession(NoInference(), store, source='keyboard')
    keyboard.fallback_session._pending_confirmation = 'old action'
    assert 'Vim' in ''.join(keyboard.stream_response('What is my preferred code editor?'))
    assert keyboard.fallback_session._pending_confirmation is None

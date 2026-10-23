"""Independent transport/consent regressions; controlled local I/O is NOT model quality."""
from __future__ import annotations
import json
import threading
import time
from dataclasses import replace
import pytest
from hanni.laya.advisory import AdvisoryClient, validate_request, validate_response
from hanni.memory.store import MemoryStore
from hanni.memory.retrieval import ContextAwareRetriever

class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, maximum):
        return self.body[:maximum]

class ControlledOpener:

    def __init__(self, mutation=None, failure=None):
        self.calls = []
        self.mutation = mutation
        self.failure = failure

    def open(self, request, timeout):
        self.calls.append(json.loads(request.data))
        if self.failure:
            raise self.failure
        payload = self.calls[-1]
        result = {'version': 1, 'request_id': payload['request_id'], 'operation': 'rank', 'uncalibrated': True, 'memory_mutated': False, 'latency_ms': 1.0, 'rankings': [{'id': row['id'], 'updated_at': row['updated_at'], 'relevant': True} for row in payload['candidates']]}
        if self.mutation:
            self.mutation(result)
        return Response(json.dumps(result).encode())

def drain(client):
    deadline = time.monotonic() + 2
    while client._queue.unfinished_tasks and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not client._queue.unfinished_tasks

def close(client):
    client.close()
    if client._worker:
        client._worker.join(timeout=2)
        assert not client._worker.is_alive()

@pytest.mark.parametrize('gates', [dict(enabled=False, quality_gate_passed=True, retrieval_enabled=True, allow_stored_memories=True), dict(enabled=True, quality_gate_passed=False, retrieval_enabled=True, allow_stored_memories=True), dict(enabled=True, quality_gate_passed=True, retrieval_enabled=False, allow_stored_memories=True), dict(enabled=True, quality_gate_passed=True, retrieval_enabled=True, allow_stored_memories=False), dict(enabled=True, quality_gate_passed=True, retrieval_enabled=True, allow_stored_memories=True, transport='remote-ssh', allow_remote_text=False, allow_remote_memories=True), dict(enabled=True, quality_gate_passed=True, retrieval_enabled=True, allow_stored_memories=True, transport='remote-ssh', allow_remote_text=True, allow_remote_memories=False)])
def test_missing_separate_gates_prevent_stored_memory_transmission(tmp_path, gates):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora benchmark achieved 84 passes')
    opener = ControlledOpener()
    client = AdvisoryClient(token='synthetic-token-with-at-least-thirty-two-characters', opener=opener, **gates)
    try:
        assert client.submit_rank('Aurora benchmark', (record,)) is False
        assert client.cached_rank('Aurora benchmark', (record,)) is None
        assert not opener.calls
        assert store.count() == 1
    finally:
        close(client)

@pytest.mark.parametrize('mutation', [lambda result: result.update(version=999), lambda result: result.update(request_id='unrelated-request'), lambda result: result.update(memory_mutated=True), lambda result: result.update(tool='memory.delete'), lambda result: result.update(latency_ms=float('nan')), lambda result: result.update(latency_ms=True), lambda result: result.update(rankings=[]), lambda result: result['rankings'][0].update(id='invented-id'), lambda result: result['rankings'][0].update(updated_at='stale-version'), lambda result: result['rankings'][0].update(relevant=1), lambda result: result['rankings'][0].update(authority='owner')])
def test_malformed_model_rankings_cannot_influence_context_or_memory(tmp_path, mutation):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora benchmark achieved 84 passes')
    opener = ControlledOpener(mutation=mutation)
    client = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, allow_stored_memories=True, token='synthetic-token-with-at-least-thirty-two-characters', opener=opener)
    try:
        fallback = ContextAwareRetriever(store).retrieve('Aurora benchmark')
        assert client.submit_rank('Aurora benchmark', (record,))
        drain(client)
        assert client.errors == 1 and client.sent == 0
        assert client.cached_rank('Aurora benchmark', (record,)) is None
        observed = ContextAwareRetriever(store, advisory=client).retrieve('Aurora benchmark')
        assert [item.record.id for item in observed.matches] == [item.record.id for item in fallback.matches]
        assert store.get(record.id) == record
    finally:
        close(client)

@pytest.mark.parametrize('failure', [TimeoutError('synthetic timeout'), ConnectionRefusedError('synthetic unavailable'), OSError('synthetic transport failure')])
def test_advisory_failures_keep_deterministic_retrieval_nonblocking(tmp_path, failure):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora benchmark achieved 84 passes')
    client = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, allow_stored_memories=True, token='synthetic-token-with-at-least-thirty-two-characters', opener=ControlledOpener(failure=failure))
    try:
        result = ContextAwareRetriever(store, advisory=client).retrieve('Aurora benchmark')
        assert record.id in [item.record.id for item in result.matches]
        drain(client)
        assert client.errors == 1
        assert not result.text.startswith('unavailable')
        assert store.get(record.id) == record
    finally:
        close(client)

def test_revision_keys_and_revoked_consent_never_return_stale_rank(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora benchmark achieved 84 passes')
    client = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, allow_stored_memories=True, token='synthetic-token-with-at-least-thirty-two-characters', opener=ControlledOpener())
    try:
        assert client.submit_rank('Aurora benchmark', (record,))
        drain(client)
        assert client.cached_rank('Aurora benchmark', (record,)) == (record.id,)
        corrected = store.correct(record.id, 'Aurora benchmark achieved 91 passes', expected_updated_at=record.updated_at.isoformat())
        assert client.cached_rank('Aurora benchmark', (corrected,)) is None
        client.allow_stored_memories = False
        assert client.cached_rank('Aurora benchmark', (record,)) is None
    finally:
        close(client)

def test_invalidation_discards_queued_stored_memories_and_inflight_cache(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    first, _ = store.remember('Aurora benchmark achieved 84 passes')
    second, _ = store.remember('Borealis benchmark achieved 93 passes')
    begun = threading.Event()
    release = threading.Event()

    class BlockingOpener(ControlledOpener):

        def open(self, request, timeout):
            begun.set()
            assert release.wait(timeout=2)
            return super().open(request, timeout)
    opener = BlockingOpener()
    client = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, allow_stored_memories=True, token='synthetic-token-with-at-least-thirty-two-characters', opener=opener)
    try:
        assert client.submit_rank('Aurora benchmark', (first,))
        assert begun.wait(timeout=1)
        assert client.submit_rank('Borealis benchmark', (second,))
        client.invalidate()
        release.set()
        drain(client)
        assert len(opener.calls) == 1
        assert client.cached_rank('Aurora benchmark', (first,)) is None
        assert client.cached_rank('Borealis benchmark', (second,)) is None
    finally:
        release.set()
        close(client)

def test_actual_memory_session_safe_mode_keeps_local_context_and_suppresses_advisory(tmp_path):
    from hanni.memory.session import MemoryAwareSession
    from hanni.core.shutdown import EmergencyStop, MemoryStopStateStore, StopSource
    from hanni.core.identity import Actor
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora benchmark achieved 84 passes')
    opener = ControlledOpener()
    client = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, allow_stored_memories=True, token='synthetic-token-with-at-least-thirty-two-characters', opener=opener)

    class Sink:
        observed = []

        def stream_response(self, prompt, **kwargs):
            self.observed.append((prompt, kwargs))
            yield 'Controlled model sink; no inference.'
    emergency = EmergencyStop(MemoryStopStateStore())
    emergency.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('synthetic-verifier'), reason='Independent Safe Mode context case')
    sink = Sink()
    session = MemoryAwareSession(sink, store, emergency_stop=emergency, extraction_enabled=False, context_retriever=ContextAwareRetriever(store, advisory=client))
    try:
        list(session.stream_response('What are the Aurora benchmark results?'))
        drain(client)
        assert not opener.calls
        assert sink.observed[0][0] == 'What are the Aurora benchmark results?'
        assert record.content in sink.observed[0][1]['memory_context']
        assert store.get(record.id) == record
    finally:
        close(client)

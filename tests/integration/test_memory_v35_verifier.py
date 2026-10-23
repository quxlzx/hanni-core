"""Independent V3.5 authorization and erasure checks using isolated synthetic data.

No trained inference, user stores, remote endpoint, SSH command or model startup.
The private HTTP and registry paths remain the original implementation.
"""
from __future__ import annotations
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4
import pytest
from hanni.core.identity import Actor
from hanni.core.shutdown import StopSource
from hanni.memory.store import MemoryStore, MemoryConflictError
from hanni.memory.retrieval import ContextAwareRetriever
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/desktop_review'))
from fixture import ReviewFixture

@pytest.fixture
def desktop():
    with ReviewFixture() as fixture:

        class EmptyVault:

            def labels(self):
                return ()

            def get(self, label):
                return None

            def preferences(self):
                return {}
        fixture.server.features.registry.google_access._vault = EmptyVault()
        try:
            yield fixture
        finally:
            from hanni.reliability.execution import close_service
            close_service(fixture.config.paths.data_dir)

def request(fixture, path, body=None, *, token=True, origin=None):
    headers = {'Origin': origin or fixture.url.rstrip('/')}
    if token:
        headers['X-Hanni-Token'] = fixture.hub.token
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(fixture.url + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method='GET' if body is None else 'POST')
    try:
        with urllib.request.urlopen(req, timeout=4) as response:
            return (response.status, json.load(response))
    except urllib.error.HTTPError as exc:
        return (exc.code, json.load(exc))

def change(operation, data, confirmed=True):
    return dict(id=str(uuid4()), operation=operation, data=data, confirmed=confirmed)

def correction(record, content, **fields):
    return dict(memory_id=record.id, expected_updated_at=record.updated_at.isoformat(), content=content, project_id='', semantic_status='statement', **fields)

@pytest.mark.parametrize('path', ['api/memory/explorer', 'api/memory/suggestions', 'api/memory/record/missing', 'api/memory/project/missing'])
def test_all_new_reads_require_original_dashboard_authentication(desktop, path):
    status, _ = request(desktop, path, token=False)
    assert status in (401, 403)
    assert desktop.server.features.memory_store().count() == 0

@pytest.mark.parametrize('confirmed,origin', [(False, None), (True, 'http://untrusted.invalid')])
def test_owner_confirmation_and_same_origin_required_before_correct(desktop, confirmed, origin):
    store = desktop.server.features.memory_store()
    record, _ = store.remember('My preferred browser is Firefox')
    status, _ = request(desktop, 'api/memory', change('correct', correction(record, 'My preferred browser is Chromium'), confirmed), origin=origin)
    assert status in (400, 401, 403)
    assert store.get(record.id).content == record.content
    assert store.history(record.id) == ()

def test_registry_safe_mode_blocks_explicit_correct_forget_and_review(desktop):
    store = desktop.server.features.memory_store()
    record, _ = store.remember('My preferred browser is Firefox')
    proposal = store.propose('add', 'My favorite drink is tea', source='synthetic:owner-turn')
    emergency = desktop.server.features.registry.context.emergency_stop
    emergency.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('synthetic-verifier'), reason='Synthetic Safe Mode case')
    bodies = [change('correct', correction(record, 'My preferred browser is Chromium')), change('forget', dict(memory_id=record.id, expected_updated_at=record.updated_at.isoformat())), change('review', dict(suggestion_id=proposal.id, expected_updated_at=proposal.updated_at.isoformat(), action='approve', edited_content=None))]
    for body in bodies:
        status, _ = request(desktop, 'api/memory', body)
        assert status >= 400
    assert store.count() == 1
    assert store.get(record.id) == record
    assert store.get_suggestion(proposal.id).status == 'pending'

def test_verified_outcome_cannot_be_claimed_in_owner_http_correction(desktop):
    store = desktop.server.features.memory_store()
    record, _ = store.remember('The synthetic benchmark is planned')
    data = correction(record, 'The synthetic benchmark completed')
    data['semantic_status'] = 'verified_outcome'
    status, _ = request(desktop, 'api/memory', change('correct', data))
    assert status >= 400
    assert store.get(record.id) == record
    assert not store.history(record.id)

def test_memory_version_conflict_rejects_stale_http_delete(desktop):
    store = desktop.server.features.memory_store()
    original, _ = store.remember('My preferred browser is Firefox')
    updated = store.correct(original.id, 'My preferred browser is Chromium', expected_updated_at=original.updated_at.isoformat())
    status, _ = request(desktop, 'api/memory', change('forget', dict(memory_id=original.id, expected_updated_at=original.updated_at.isoformat())))
    assert status >= 400
    assert store.get(original.id) == updated

@pytest.mark.parametrize('review_status', ['pending', 'rejected', 'dismissed'])
def test_delete_erases_source_bound_suggestion_in_every_review_state(tmp_path, review_status):
    store = MemoryStore(tmp_path / 'memory.db')
    original, _ = store.remember('My preferred browser is Firefox', source_ref='synthetic:source-1')
    revised = store.correct(original.id, 'My preferred browser is Chromium', expected_updated_at=original.updated_at.isoformat())
    proposal = store.propose('conflict', 'Current browser choice needs review', source='synthetic:analysis', related_ids=(original.id,))
    if review_status != 'pending':
        action = 'reject' if review_status == 'rejected' else 'dismiss'
        store.review_suggestion(proposal.id, action, expected_updated_at=proposal.updated_at.isoformat())
    store.delete(original.id, expected_updated_at=revised.updated_at.isoformat())
    assert store.get_suggestion(proposal.id) is None
    assert store.history(original.id) == ()
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM memory_history').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM memory_suggestions').fetchone()[0] == 0
    assert store.search('browser') == ()

def test_delete_erases_approved_add_receipt_and_no_reappearance(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    proposal = store.propose('add', 'My favorite drink is tea', source='synthetic:owner-turn', source_ref='synthetic:source-2')
    receipt = store.review_suggestion(proposal.id, 'approve', expected_updated_at=proposal.updated_at.isoformat())
    record = store.list()[0]
    assert receipt.target_id == record.id
    store.delete(record.id)
    assert store.get_suggestion(proposal.id) is None
    assert ContextAwareRetriever(store).retrieve('favorite drink').matches == ()
    assert MemoryStore(store.path).count() == 0

def test_review_conflict_and_edited_secret_do_not_change_authoritative_store(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    existing, _ = store.remember('My preferred browser is Firefox')
    proposal = store.propose('add', 'My preferred browser is Chromium', source='synthetic:owner-turn')
    with pytest.raises(MemoryConflictError):
        store.review_suggestion(proposal.id, 'approve', expected_updated_at=proposal.updated_at.isoformat())
    safe = store.propose('add', 'My favorite drink is tea', source='synthetic:owner-turn')
    with pytest.raises(ValueError):
        store.review_suggestion(safe.id, 'approve', expected_updated_at=safe.updated_at.isoformat(), edited_content='My password is synthetic-no-real-secret')
    assert store.count() == 1
    assert store.get(existing.id) == existing
    assert store.get_suggestion(safe.id).status == 'pending'

def test_retrieval_uses_current_revision_after_cross_process_correct_delete(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora benchmark currently has 84 passes', project_id='synthetic-project')
    retriever = ContextAwareRetriever(store, project_id='synthetic-project')
    assert any((m.record.id == record.id for m in retriever.retrieve('Aurora benchmark').matches))
    other = MemoryStore(store.path)
    revision = other.correct(record.id, 'Aurora benchmark currently has 91 passes', expected_updated_at=record.updated_at.isoformat())
    current = retriever.retrieve('Aurora benchmark')
    assert '91 passes' in current.text
    assert '84 passes' not in current.text
    other.delete(record.id, expected_updated_at=revision.updated_at.isoformat())
    assert retriever.retrieve('Aurora benchmark').text == ''

def test_imported_secret_and_injection_are_not_retrieved_or_browsed(desktop):
    store = desktop.server.features.memory_store()
    safe, _ = store.remember('Aurora benchmark result is 84 passes')
    with store._connect() as db:
        db.execute('UPDATE memories SET content=?,normalized_content=? WHERE id=?', ('Aurora password is synthetic-legacy-secret', 'legacy-secret', safe.id))
    assert ContextAwareRetriever(store).retrieve('Aurora password').matches == ()
    status, view = request(desktop, 'api/memory/explorer')
    assert status == 200
    assert view['records'] == []
    assert 'synthetic-legacy-secret' not in json.dumps(view)

def test_utf8_budgets_preserve_json_and_record_provenance(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('Aurora label is jellyfish and café', source_ref='synthetic:unicode-source')
    retriever = ContextAwareRetriever(store, max_chars=1600, max_tokens=1600, limit=5)
    result = retriever.retrieve('Aurora label')
    assert result.matches
    assert len(result.text) <= 1600 and len(result.text.encode('utf-8')) <= 1600
    obj = json.loads(result.text)
    assert obj['memories'][0]['id'] == record.id
    assert obj['memories'][0]['source_ref'] == 'synthetic:unicode-source'
    assert obj['memories'][0]['verification_status'] != 'verified_record'

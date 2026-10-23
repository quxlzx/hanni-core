"""Native corrupt-row recovery and configured fallback budget contracts."""
from dataclasses import replace
import pytest
from hanni.core.shutdown import Actor, StopSource
from hanni.memory.integration import configured_retriever
from hanni.memory.retrieval import MemoryContext
from hanni.memory.session import MemoryAwareSession
from hanni.memory.store import MemoryStore
from tests.integration.test_campaign3_boundaries import Capture, feature, say

@pytest.mark.parametrize('field', ['created_at', 'updated_at', 'confidence'])
@pytest.mark.parametrize('prompt', ['What do you remember?', 'Show memories about Aurora', 'Which folder is my Aurora project?', 'Show my Aurora project', 'Open my Aurora project', 'Forget Aurora', 'Delete everything you remember about Aurora'])
def test_corrupt_row_is_reported_without_escaping_or_fabricating_memory(tmp_path, field, prompt):
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    row, _ = store.remember('my Aurora project is C:\\Synthetic\\Aurora')
    fallback = Capture()
    session = MemoryAwareSession(fallback, store, extraction_enabled=False)
    invalid = 'password is example-public-63ca43501dff-corrupt-value'
    with store._connect() as db:
        if field == 'confidence':
            db.execute('PRAGMA ignore_check_constraints=ON')
        db.execute(f'UPDATE memories SET {field}=? WHERE id=?', (invalid, row.id))
    reply = say(session, prompt)
    assert 'memory' in reply.lower() and ('available' in reply.lower() or 'read' in reply.lower())
    assert invalid not in reply and 'example-public-63ca43501dff-corrupt-value' not in reply
    assert not fallback.calls and 'C:\\Synthetic\\Aurora' not in reply
    with store._connect() as db:
        assert db.execute('SELECT count(*) FROM memories').fetchone()[0] == 1

@pytest.mark.parametrize('budget', [128, 256, 512])
def test_native_legacy_factory_honors_configured_context_byte_budget(tmp_path, budget):
    app = feature(tmp_path)
    store = app.memory_store()
    store.remember('My preferred code editor is Lapce', source='owner_explicit:controlled')
    config = replace(app.config, hanni=replace(app.config.hanni, memory=replace(app.config.hanni.memory, context_enabled=False, max_context_tokens=budget)))
    try:
        reader = configured_retriever(config, store)
        assert reader.max_tokens == budget
        result = reader.retrieve('Which code editor do I prefer?')
        assert len(result.text.encode('utf-8')) <= budget
    finally:
        from hanni.laya.runtime import stop_advisory
        stop_advisory(config)

@pytest.mark.parametrize('failure', ['optional_outage', 'safe_mode'])
@pytest.mark.parametrize('budget', [128, 256, 512])
def test_original_session_fallback_cannot_relax_trusted_context_budget(tmp_path, failure, budget):
    app = feature(tmp_path)
    store = app.memory_store()
    store.remember('My preferred code editor is Lapce', source='owner_explicit:controlled')

    class BoundedUnavailable:
        max_tokens = budget

        def retrieve(self, _):
            raise ConnectionError('Controlled optional context outage')
    fallback = Capture()
    session = MemoryAwareSession(fallback, store, extraction_enabled=False, registry=app.registry, context_retriever=BoundedUnavailable())
    if failure == 'safe_mode':
        app.registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('campaign3-budget'), reason='Controlled fallback path')
    say(session, 'Which code editor do I prefer?')
    assert fallback.calls
    context = fallback.calls[-1][1].get('memory_context', '')
    assert len(context.encode('utf-8')) <= budget
    assert session._fallback_retriever.max_tokens == budget

@pytest.mark.parametrize('level', [0, 1, 2])
@pytest.mark.parametrize('explicit', [False, True])
def test_fresh_key_automatic_capture_requires_existing_tier_two_but_explicit_owner_command_is_preserved(tmp_path, level, explicit):
    app = feature(tmp_path)
    config = app.config
    profile = replace(config.permissions.profiles['owner'], chat_only=False, max_auto_approve_level=level)
    config = replace(config, permissions=replace(config.permissions, profiles={**config.permissions.profiles, 'owner': profile}))
    from hanni.dashboard.features import DesktopFeatures
    authority = DesktopFeatures(config).registry
    store = app.memory_store()
    assert store.count() == 0, 'Fresh preference must not be hidden by an existing conflict'
    prompt = 'I prefer concise answers'
    if explicit:
        prompt = 'Remember ' + prompt
    reply = say(MemoryAwareSession(Capture(), store, registry=authority), prompt)
    permitted = explicit or level == 2
    assert store.count() == int(permitted)
    if permitted:
        assert 'saved' in reply or 'remember' in reply
    else:
        assert 'saved' not in reply and 'remember:' not in reply

def test_normal_conversation_generation_errors_are_not_mislabeled_as_memory_corruption(tmp_path):

    class BrokenModel:

        def stream_response(self, *_args, **_kwargs):
            raise ValueError('Controlled model transport error, not memory data')
            yield ''
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    session = MemoryAwareSession(BrokenModel(), store, extraction_enabled=False)
    with pytest.raises(ValueError, match='model transport'):
        say(session, 'Tell me about rain clouds')

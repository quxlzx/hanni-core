"""Actual local storage/session integration; model generation is a named fixture."""
from dataclasses import replace
import json
from uuid import uuid4
import pytest
from hanni.config import load_config
from hanni.core.orchestrator import TextSession
from hanni.dashboard.productivity import ProductivityStore
from hanni.memory.integration import PersonalContextProvider, configured_retriever
from hanni.memory.projects import ProjectContext
from hanni.memory.retrieval import ContextAwareRetriever, LocalMemoryRetriever
from hanni.memory.session import MemoryAwareSession
from hanni.memory.store import MemoryStore
from tests.helpers import write_config_dir

class CaptureSession:

    def __init__(self):
        self.calls = []
        self.invalidations = 0

    def stream_response(self, prompt, **kwargs):
        self.calls.append((prompt, dict(kwargs)))
        yield 'fixture response'

    def invalidate_memory_context(self):
        self.invalidations += 1

def project(workspace, name):
    return workspace.mutate('project.create', {'name': name, 'description': 'Local model development'}, str(uuid4()))['project']

def environment(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    workspace = ProductivityStore(tmp_path)
    projects = ProjectContext(store, workspace)
    provider = PersonalContextProvider(store, project_context=projects)
    fallback = CaptureSession()
    session = MemoryAwareSession(fallback, store, context_retriever=provider, extraction_enabled=False)
    return (store, workspace, provider, fallback, session)

def say(session, prompt):
    return ''.join(session.stream_response(prompt))

def test_continuity_uses_approved_project_state_without_claiming_execution(tmp_path):
    store, workspace, provider, fallback, session = environment(tmp_path)
    item = project(workspace, '4B model')
    record, _ = store.remember('I decided to use Qwen for the next benchmark', project_id=item['id'])
    say(session, 'Continue where we left off with my 4B model')
    payload = fallback.calls[-1][1]['memory_context']
    assert record.id in payload and record.content in payload
    assert 'Approved decision' in payload
    assert 'Verified current state: Not established.' in payload
    assert store.count() == 1 and (not store.suggestions())
    assert len(payload) <= provider.max_chars
    assert len(payload.encode('utf-8')) <= provider.max_tokens

def test_ambiguous_continuation_never_reaches_model_or_mutates_memory(tmp_path):
    store, workspace, _, fallback, session = environment(tmp_path)
    project(workspace, '4B model')
    project(workspace, '7B model')
    before = store.fingerprint()
    reply = say(session, 'Continue the model project')
    assert 'Which project' in reply and '4B model' in reply and ('7B model' in reply)
    assert not fallback.calls and store.fingerprint() == before

def test_resume_playback_is_not_intercepted_by_project_resolution(tmp_path):
    _, workspace, _, fallback, session = environment(tmp_path)
    project(workspace, '4B model')
    project(workspace, '7B model')
    assert say(session, 'Resume playback') == 'fixture response'
    assert fallback.calls[-1][0] == 'Resume playback'

def test_explicit_unique_alias_continuation_uses_actual_project(tmp_path):
    store, workspace, provider, fallback, session = environment(tmp_path)
    item = project(workspace, 'Aurora evaluation')
    provider.project_context.add_alias(item['id'], 'Aurora', expected_fingerprint=item['fingerprint'])
    record, _ = store.remember('I decided to compare the two model exports', project_id=item['id'])
    say(session, 'Continue Aurora')
    assert record.id in fallback.calls[-1][1]['memory_context']

def test_project_and_global_recall_share_record_and_utf8_budgets(tmp_path):
    store, workspace, _, fallback, _ = environment(tmp_path)
    item = project(workspace, '4B model')
    store.remember('The model export needs a tokenizer review', project_id=item['id'])
    store.remember('I prefer concise explanations for model debugging')
    provider = PersonalContextProvider(store, project_context=ProjectContext(store, workspace), limit=1)
    result = provider.retrieve('Continue the 4B model project')
    assert len(result.matches) <= 1
    assert len(result.text) <= provider.max_chars
    assert len(result.text.encode('utf-8')) <= provider.max_tokens

def test_cross_process_correction_and_forget_remove_old_context(tmp_path):
    store, workspace, _, fallback, session = environment(tmp_path)
    item = project(workspace, '4B model')
    original, _ = store.remember('The model project has an unresolved tokenizer issue', project_id=item['id'])
    say(session, 'Continue my 4B model project')
    assert original.content in fallback.calls[-1][1]['memory_context']
    external = MemoryStore(store.path)
    current = external.correct(original.id, 'The model project has an unresolved export issue', expected_updated_at=original.updated_at.isoformat())
    say(session, 'Continue my 4B model project')
    after = fallback.calls[-1][1]['memory_context']
    assert current.content in after and original.content not in after
    external.delete(current.id, expected_updated_at=current.updated_at.isoformat())
    say(session, 'Continue my 4B model project')
    assert current.content not in fallback.calls[-1][1]['memory_context']
    assert not external.history(current.id) and fallback.invalidations >= 2

def test_optional_context_outage_uses_existing_deterministic_recall(tmp_path):

    class Unavailable:

        def retrieve(self, _goal):
            raise ConnectionError('Optional service unavailable')
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    item, _ = store.remember('My preferred code editor is VS Code')
    fallback = CaptureSession()
    session = MemoryAwareSession(fallback, store, context_retriever=Unavailable(), extraction_enabled=False)
    say(session, 'Explain my saved code editor preference.')
    assert item.id in fallback.calls[-1][1]['memory_context']
    assert store.count() == 1

def test_enhanced_context_is_opted_and_project_outage_does_not_break_startup(tmp_path, monkeypatch):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    store = MemoryStore(config.paths.data_dir / config.hanni.memory.database_file)
    assert isinstance(configured_retriever(config, store), LocalMemoryRetriever)
    enabled = replace(config, hanni=replace(config.hanni, memory=replace(config.hanni.memory, context_enabled=True)))

    def unavailable(*args, **kwargs):
        raise OSError('Project database unavailable')
    monkeypatch.setattr(ProjectContext, 'from_config', unavailable)
    assert isinstance(configured_retriever(enabled, store), ContextAwareRetriever)

def test_unrelated_chat_does_not_receive_project_details(tmp_path):
    _, workspace, _, fallback, session = environment(tmp_path)
    project(workspace, '4B model')
    say(session, 'Good morning')
    assert 'memory_context' not in fallback.calls[-1][1]

def test_retrieval_context_does_not_enter_conversation_cache_and_current_request_stays_last(tmp_path):

    class ModelFixture:

        def __init__(self):
            self.messages = []

        def stream_chat(self, messages, **kwargs):
            self.messages.append(messages)
            yield 'fixture answer'
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    record, _ = store.remember('My preferred code editor is VS Code')
    model = ModelFixture()
    text = TextSession(model)
    session = MemoryAwareSession(text, store, context_retriever=ContextAwareRetriever(store), extraction_enabled=False)
    request = 'Give me a detailed explanation of the code editor choice'
    say(session, request)
    assert record.id in model.messages[-1][-2]['content']
    assert model.messages[-1][-1]['content'] == request
    assert 'current owner request wins' in model.messages[-1][0]['content'].lower()
    assert text.history == ()

def test_utf8_budget_omits_whole_records_instead_of_truncating_json(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite3')
    store.remember('My preferred code editor label is ' + '猫' * 80)
    provider = PersonalContextProvider(store, max_chars=4000, max_tokens=1000)
    result = provider.retrieve('Which code editor label do I use?')
    assert len(result.text.encode('utf-8')) <= 1000
    if result.text:
        decoded = json.loads(result.text)
        assert all((item['content'].endswith('猫' * 80) for item in decoded['memories']))

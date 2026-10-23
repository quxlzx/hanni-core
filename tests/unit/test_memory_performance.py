"""Prepared lexical terms must obey the live privacy gate on every recall."""
from __future__ import annotations
import pytest
from hanni.logs.redaction import clear_registry, register_secret, secret_registry_revision
from hanni.memory.retrieval import ContextAwareRetriever
from hanni.memory.store import MemoryStore

@pytest.fixture(autouse=True)
def isolated_secret_registry():
    clear_registry()
    yield
    clear_registry()

def recall_fixture(tmp_path):
    store = MemoryStore(tmp_path / 'memory.db')
    record, _ = store.remember('The atlas benchmark label is synthetic-ridge-8427')
    retriever = ContextAwareRetriever(store)
    assert retriever.retrieve('atlas benchmark').matches[0].record.id == record.id
    return (store, record, retriever)

def test_newly_registered_secret_invalidates_warm_memory_validation(tmp_path):
    _, _, retriever = recall_fixture(tmp_path)
    register_secret('synthetic_dynamic_audit', 'synthetic-ridge-8427')
    recalled = retriever.retrieve('atlas benchmark')
    assert recalled.text == ''
    assert recalled.matches == ()
    assert retriever.last_metrics['records'] == 0
    assert not retriever._prepared_terms

def test_secret_rotation_revalidates_previous_and_current_values(tmp_path):
    store, old, retriever = recall_fixture(tmp_path)
    new, _ = store.remember('The atlas benchmark label is synthetic-cove-6139')
    assert len(retriever.retrieve('atlas benchmark').matches) == 2
    register_secret('synthetic_rotating_audit', 'synthetic-ridge-8427')
    assert [match.record.id for match in retriever.retrieve('atlas benchmark').matches] == [new.id]
    register_secret('synthetic_rotating_audit', 'synthetic-cove-6139')
    assert [match.record.id for match in retriever.retrieve('atlas benchmark').matches] == [old.id]

def test_clear_and_reregister_cannot_reuse_prior_policy_epoch(tmp_path):
    _, _, retriever = recall_fixture(tmp_path)
    original_epoch = secret_registry_revision()
    register_secret('synthetic_dynamic_audit', 'synthetic-ridge-8427')
    assert not retriever.retrieve('atlas benchmark').matches
    clear_registry()
    assert retriever.retrieve('atlas benchmark').matches
    register_secret('synthetic_dynamic_audit', 'synthetic-ridge-8427')
    assert secret_registry_revision() > original_epoch
    assert not retriever.retrieve('atlas benchmark').matches

def test_registry_revision_ignores_noops_and_never_reuses_clear_epoch():
    initial = secret_registry_revision()
    register_secret('synthetic_noop', 'short')
    assert secret_registry_revision() == initial
    register_secret('synthetic_noop', 'synthetic-ridge-8427')
    registered = secret_registry_revision()
    assert registered > initial
    register_secret('synthetic_noop', 'synthetic-ridge-8427')
    assert secret_registry_revision() == registered
    clear_registry()
    assert secret_registry_revision() > registered

def test_mid_scan_secret_registration_fails_closed_before_advisory(tmp_path, monkeypatch):
    store, _, retriever = recall_fixture(tmp_path)
    original_iter = store.iter_records
    called = []

    def mutating_records(**kwargs):
        for record in original_iter(**kwargs):
            yield record
        register_secret('synthetic_mid_scan', 'synthetic-ridge-8427')

    class Advisory:

        def submit_rank(self, *args, **kwargs):
            called.append(args)
    retriever.advisory = Advisory()
    monkeypatch.setattr(store, 'iter_records', mutating_records)
    assert retriever.retrieve('atlas benchmark').text == ''
    assert not called
    assert not retriever._prepared_terms

def test_mid_advisory_registration_fails_closed_before_context_return(tmp_path):
    _, _, retriever = recall_fixture(tmp_path)

    class Advisory:

        def submit_rank(self, *args, **kwargs):
            register_secret('synthetic_mid_advisory', 'synthetic-ridge-8427')

        def cached_rank(self, *args):
            return None
    retriever.advisory = Advisory()
    recalled = retriever.retrieve('atlas benchmark')
    assert recalled.text == ''
    assert recalled.matches == ()
    assert not retriever._prepared_terms
    assert retriever.last_metrics['records'] == 0

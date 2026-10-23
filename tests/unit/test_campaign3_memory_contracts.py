"""Development regressions for original SQLite and retrieval safety boundaries."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pytest
from hanni.laya.intelligence import analyze_candidate, analyze_relationships, analyze_statement, classify_semantic_status
from hanni.memory.retrieval import ContextAwareRetriever, LocalMemoryRetriever
from hanni.memory.store import MemoryConflictError, MemoryStore
from scripts.campaign3.development_corpus import CATEGORIES
from scripts.campaign3.retrieval_harness import run_case
ROOT = Path(__file__).resolve().parents[2]

def update(store, identity, **values):
    with store._connect() as db:
        db.execute('UPDATE memories SET ' + ','.join((name + '=?' for name in values)) + ' WHERE id=?', (*values.values(), identity))

@pytest.mark.parametrize('retriever', [LocalMemoryRetriever, ContextAwareRetriever])
@pytest.mark.parametrize('field', ['source', 'source_ref', 'fact_key', 'fact_value', 'project_id', 'memory_type'])
def test_warm_recall_revalidates_changed_metadata_without_timestamp(tmp_path, retriever, field):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    record, _ = store.remember('The synthetic report color is turquoise.')
    original_time = record.updated_at
    recall = retriever(store)
    assert [item.record.id for item in recall.retrieve('report color').matches] == [record.id]
    update(store, record.id, **{field: 'synthetic password NEVER_REAL'})
    assert store.get(record.id).updated_at == original_time
    result = recall.retrieve('report color')
    assert result.matches == () and result.text == ''

@pytest.mark.parametrize('retriever', [LocalMemoryRetriever, ContextAwareRetriever])
@pytest.mark.parametrize('status', ['temporary', 'question', 'hypothetical', 'inference'])
def test_epistemic_candidates_are_not_owner_preferences(tmp_path, retriever, status):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    store.remember('The synthetic browser preference is Falcon.', semantic_status=status)
    assert retriever(store).retrieve('browser preference').text == ''

@pytest.mark.parametrize('retriever', [LocalMemoryRetriever, ContextAwareRetriever])
def test_exclusions_apply_before_top_k_and_do_not_reintroduce_deleted_sources(tmp_path, retriever):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    kept, _ = store.remember('The release report reviewer is the synthetic team.')
    excluded = []
    for number in range(110):
        row, _ = store.remember('The release report reviewer is synthetic distractor ' + str(number) + '.')
        excluded.append(row.id)
    recall = retriever(store, limit=1)
    result = recall.retrieve('release report reviewer', exclude_ids=excluded)
    assert [item.record.id for item in result.matches] == [kept.id]
    store.delete(kept.id)
    assert recall.retrieve('release report reviewer', exclude_ids=excluded).matches == ()

@pytest.mark.parametrize('field,value', [('content', 'The sample report label is azure.'), ('source_ref', 'synthetic:revised'), ('semantic_status', 'question'), ('project_id', 'revised-project')])
def test_fingerprint_detects_actual_content_and_metadata_when_revision_is_unchanged(tmp_path, field, value):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    row, _ = store.remember('The sample report label is amber.')
    before = store.fingerprint()
    update(store, row.id, **{field: value})
    assert store.get(row.id).updated_at == row.updated_at
    assert store.fingerprint() != before
    assert store.fingerprint() == MemoryStore(store.path).fingerprint()

def test_distinct_projects_preserve_their_keyed_preferences_and_corrections(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    first, _ = store.remember('My preferred editor is Helix.', project_id='alpha')
    second, _ = store.remember('My preferred editor is Kate.', project_id='beta')
    assert first.id != second.id
    assert store.get(first.id).fact_value == 'Helix'
    revised = store.correct(first.id, 'My preferred editor is Vim.', expected_updated_at=first.updated_at.isoformat())
    assert revised.project_id == 'alpha' and revised.fact_value == 'Vim'
    assert store.get(second.id).fact_value == 'Kate'
    assert [record.id for record in store.by_key(first.fact_key, project_id='alpha')] == [first.id]
    assert len(store.by_key(first.fact_key)) == 2
    assert not [row for row in analyze_relationships(store.iter_records()) if row.kind == 'conflict']
    proposal = replace(analyze_statement('My preferred editor is Kakoune.'), project_id='alpha')
    assert [row.memory_ids for row in analyze_candidate(proposal, store.iter_records())] == [(first.id,)]

def test_identical_text_cannot_silently_move_to_a_different_project(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    row, _ = store.remember('The shared report uses plain text.', project_id='alpha')
    before = store.fingerprint()
    with pytest.raises(MemoryConflictError, match='another project'):
        store.remember(row.content, project_id='beta')
    assert store.fingerprint() == before and store.get(row.id).project_id == 'alpha'

def test_scoped_key_replacement_reports_normalized_collision_without_partial_mutation(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    first, _ = store.remember('My preferred editor is Vim.', project_id='alpha')
    second, _ = store.remember('My preferred editor is Helix.', project_id='beta')
    before = store.fingerprint()
    with pytest.raises(MemoryConflictError, match='another project'):
        store.remember(second.content, project_id='alpha')
    assert store.fingerprint() == before
    assert store.get(first.id).fact_value == 'Vim' and store.get(second.id).fact_value == 'Helix'

def test_owner_review_can_add_an_independent_project_preference_without_global_merge(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    first, _ = store.remember('My preferred editor is Helix.', project_id='alpha')
    proposal = store.propose('add', 'My preferred editor is Kate.', project_id='beta', source='synthetic-development')
    reviewed = store.review_suggestion(proposal.id, 'approve', expected_updated_at=proposal.updated_at.isoformat())
    assert reviewed.status == 'approved'
    assert store.get(first.id).fact_value == 'Helix'
    assert [row.fact_value for row in store.by_key(first.fact_key, project_id='beta')] == ['Kate']

@pytest.mark.parametrize('text', ['I have not finished the package installation.', 'The workflow has never passed its checks.', 'The export was not saved.', "I haven't uploaded the report.", 'The test was canceled before execution.', 'The run was aborted by the operator.', 'The project stopped without completing its migration.', 'The notebook was not published.'])
def test_negated_or_cancelled_completion_never_becomes_a_success_claim(text):
    assert classify_semantic_status(text) == 'failed_claim'

@pytest.mark.parametrize('text,status', [('I will not publish the project yet.', 'plan'), ('Did the test fail?', 'question'), ('Maybe the project did not finish.', 'hypothetical'), ('I completed the project but its checksum is unchecked.', 'completed_claim'), ('The workflow not only finished but passed.', 'completed_claim')])
def test_epistemic_precedence_and_positive_completion_are_preserved(text, status):
    assert classify_semantic_status(text) == status

@pytest.mark.parametrize('retriever', [LocalMemoryRetriever, ContextAwareRetriever])
def test_verified_metadata_is_historical_not_current_state_observation(tmp_path, retriever):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    row, _ = store.remember('The synthetic workflow report was checked.', semantic_status='verified_outcome', source='workflow_verified:synthetic')
    result = retriever(store).retrieve('workflow report')
    record = json.loads(result.text)['memories'][0]
    assert record['verification_status'] == 'historical_workflow_verification_record'
    assert record['current_state_verified'] is False
    update(store, row.id, source='external_document:synthetic')
    assert retriever(store).retrieve('workflow report').text == ''

@pytest.mark.parametrize('retriever', [LocalMemoryRetriever, ContextAwareRetriever])
def test_utf8_budget_preserves_whole_records_and_honest_metrics(tmp_path, retriever):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    store.remember('The report title is 三百毫秒。')
    recall = retriever(store, max_tokens=128)
    result = recall.retrieve('report title')
    assert result.matches == () and result.text == ''
    assert recall.last_metrics['estimated_tokens'] == len(result.text.encode('utf-8'))
    assert recall.last_metrics['token_estimator'] == 'utf8_byte_upper_bound'

def test_optional_advisory_revision_guard_checks_content_not_only_time(tmp_path):
    store = MemoryStore(tmp_path / 'memory.sqlite')
    record, _ = store.remember('The benchmark dataset is amber.')

    class Leaf:

        def submit_rank(self, query, records, validation):
            self.validation = validation

        def cached_rank(self, *args):
            return None
    leaf = Leaf()
    recall = ContextAwareRetriever(store, advisory=leaf)
    assert recall.retrieve('benchmark dataset').matches
    assert leaf.validation() is True
    update(store, record.id, content='The benchmark dataset is cobalt.')
    assert leaf.validation() is False

def test_development_corpus_freeze_and_category_denominators():
    path = ROOT / 'evals/memory/campaign3_development.jsonl'
    manifest = json.loads((path.parent / 'campaign3_development_manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sha256']
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    assert len(rows) >= 320 and len({row['id'] for row in rows}) == len(rows)
    assert set((row['category'] for row in rows)) == set(CATEGORIES)
    assert all((sum((row['category'] == category for row in rows)) >= 16 for category in CATEGORIES))
    assert sum((bool(row['expected']['relevant_ids']) for row in rows)) == manifest['positive_cases']
    assert sum((not row['expected']['relevant_ids'] for row in rows)) == manifest['negative_cases']

def test_runner_does_not_treat_unexpected_action_errors_or_missing_rejections_as_pass(tmp_path):
    case = {'id': 'harness-action-proof', 'category': 'corrections', 'memories': [], 'query': None, 'operations': [{'op': 'delete', 'target_id': 'nonexistent'}]}
    result = run_case(case, tmp_path / 'first.sqlite')
    assert result['passed'] is False
    case = {'id': 'harness-rejection-proof', 'category': 'privacy and sensitivity handling', 'memories': [{'id': 'allowed', 'content': 'The synthetic report title is safe.', 'expect_rejection': True}], 'query': None}
    result = run_case(case, tmp_path / 'second.sqlite')
    assert result['passed'] is False and result['setup_errors'][0]['error']['type'] == 'ExpectedRejectionMissing'

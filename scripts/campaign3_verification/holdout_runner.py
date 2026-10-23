"""Oracle-free original-memory execution and once-only independent sealing.

This module never loads expected answers. Scoring is a separate boundary.
All record labels and explicit scopes come from author inputs, not retrieval.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sqlite3
import time
import uuid
import zipfile
from hanni.memory.store import MemoryStore
from hanni.memory.retrieval import LocalMemoryRetriever, ContextAwareRetriever
ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / 'data/campaign3-verifier'

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding='utf8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_manifest():
    paths = set((ROOT / 'src').rglob('*.py'))
    paths.update((ROOT / 'config').glob('*.yaml'))
    for pattern in ('scripts/campaign3*', 'tests/integration/test_campaign3*'):
        for entry in ROOT.glob(pattern):
            if entry.is_dir():
                paths.update(entry.rglob('*.py'))
            elif entry.suffix == '.py':
                paths.add(entry)
    paths.update(ROOT.glob('docs/campaign3/*PROTOCOL*.md'))
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}

def freeze(output):
    output.mkdir(parents=True, exist_ok=False)
    proof = {'captured_at': datetime.now(timezone.utc).isoformat(), 'files': source_manifest()}
    archive = output / 'source.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, expected in proof['files'].items():
            raw = (ROOT / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise RuntimeError('Source changed during snapshot')
            zipped.writestr(name, raw)
    proof['archive_sha256'] = digest(archive)
    save(output / 'proof.json', proof)
    return proof

def run_case(case, output, arm):
    """Only input fixtures cross this boundary; original implementations retained."""
    if 'expected' in case or 'phases' in case:
        raise ValueError('Oracles must not cross execution boundary')
    output.mkdir(parents=True, exist_ok=False)
    db_path = output / 'memory.sqlite3'
    store = MemoryStore(db_path)
    labels, projects, original_revisions = ({}, {}, {})
    seeds, actions, retrievals = ([], [], [])
    options = {'limit': 5, 'max_chars': 4000, 'max_tokens': 4000, 'min_score': 25.0}
    options.update(case.get('options', {}))
    owned_advisory, fault_opener, project_context = (None, None, None)

    def error(exc):
        return dict(type=type(exc).__name__, message=str(exc))

    def snapshot():
        try:
            return [row.to_dict() for row in store.iter_records()]
        except Exception as exc:
            return {'error': error(exc)}

    def safe_call(callback):
        try:
            return callback()
        except Exception as exc:
            return {'error': error(exc)}
    if case.get('projects'):
        from hanni.dashboard.productivity import ProductivityStore
        from hanni.memory.projects import ProjectContext
        workspace = ProductivityStore(output / 'workspace')
        project_context = ProjectContext(store, workspace)
        for item in case['projects']:
            project = workspace.mutate('project.create', dict(name=item['name'], description=item.get('description', '')), str(uuid.uuid4()))['project']
            projects[item['id']] = project['id']
            for alias in item.get('aliases', []):
                current = project_context.project(project['id'])
                project_context.add_alias(project['id'], alias, expected_fingerprint=current['fingerprint'])
    if case.get('advisory_mode') and arm == 'context':
        from hanni.laya.advisory import AdvisoryClient
        from scripts.campaign3.retrieval_harness import FaultOpener
        fault_opener = FaultOpener(case['advisory_mode'])
        owned_advisory = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, allow_stored_memories=True, token='campaign3-independent-synthetic-authorization-only', timeout_seconds=0.05, opener=fault_opener)

    def remember(item):
        metadata = {key: item[key] for key in ('source', 'source_ref', 'semantic_status', 'memory_type') if key in item}
        metadata['project_id'] = projects.get(item.get('project_id', ''), item.get('project_id', ''))
        record, created = store.remember(item['content'], **metadata)
        labels[item['id']] = record.id
        original_revisions.setdefault(item['id'], record.updated_at.isoformat())
        return dict(logical_id=item['id'], actual_id=record.id, created=created, record=record.to_dict())
    for item in case.get('memories', []):
        row = {'logical_id': item['id']}
        try:
            row.update(remember(item))
        except Exception as exc:
            row['error'] = error(exc)
        seeds.append(row)

    def new_retriever():
        common = {key: options[key] for key in ('limit', 'max_chars', 'min_score')}
        scope = projects.get(case.get('project_id', ''), case.get('project_id', ''))
        if arm == 'legacy':
            parameters = inspect.signature(LocalMemoryRetriever).parameters
            if 'max_tokens' in parameters:
                common['max_tokens'] = options['max_tokens']
            if 'project_id' in parameters:
                common['project_id'] = scope
            return LocalMemoryRetriever(store, **common)
        return ContextAwareRetriever(store, max_tokens=options['max_tokens'], project_id=scope, advisory=owned_advisory, **common)
    retriever = new_retriever()

    def retrieve(query, phase):
        receipt = dict(phase=phase, query=query, arm=arm, logical_ids=[], records=[], context_text='')
        before = snapshot()
        started = time.perf_counter()
        try:
            context = retriever.retrieve(query)
            reverse = {actual: logical for logical, actual in labels.items()}
            records = [{**match.record.to_dict(), 'logical_id': reverse.get(match.record.id), 'score': match.score, 'score_kind': 'uncalibrated heuristic'} for match in context.matches]
            receipt.update(logical_ids=[record['logical_id'] for record in records], records=records, context_text=context.text, context_utf8_bytes=len(context.text.encode('utf8')), context_chars=len(context.text), production_metrics=dict(getattr(retriever, 'last_metrics', {})))
        except Exception as exc:
            receipt['error'] = error(exc)
        receipt['retrieval_ms'] = (time.perf_counter() - started) * 1000
        after = snapshot()
        receipt.update(authoritative_store_unchanged=before == after, store_before=before, store_after=after, token_measurement='UTF-8 bytes, not actual model tokens')
        retrievals.append(receipt)
        return receipt
    try:
        for index, operation in enumerate(case.get('operations', [])):
            row = dict(index=index, op=operation['op'], before=snapshot())
            try:
                name = operation['op']
                if name == 'retrieve':
                    row['retrieval_index'] = len(retrievals)
                    retrieve(operation.get('query', case['query']), f'warm-{index}')
                elif name == 'restart':
                    store = MemoryStore(db_path)
                    if project_context:
                        project_context.store = store
                    retriever = new_retriever()
                    row['original_store_reopened'] = True
                elif name == 'correct':
                    current = store.get(labels[operation['target_id']])
                    revision = original_revisions[operation['target_id']] if operation.get('revision') == 'original' else current.updated_at.isoformat()
                    metadata = {key: operation[key] for key in ('semantic_status', 'source_ref') if key in operation}
                    row['result'] = store.correct(current.id, operation['content'], expected_updated_at=revision, **metadata).to_dict()
                elif name == 'delete':
                    row['deleted'] = store.delete(labels[operation['target_id']])
                elif name == 'remember':
                    item = dict(id=operation['target_id'], content=operation['content'], source='owner_explicit:fixture')
                    if 'source_ref' in operation:
                        item['source_ref'] = operation['source_ref']
                    row['result'] = remember(item)
                elif name == 'propose':
                    current = store.get(labels[operation['target_id']])
                    proposal = store.propose(operation['kind'], operation['content'], source='controlled_fixture:proposal', target_id=current.id, expected_updated_at=current.updated_at.isoformat())
                    row['result'] = proposal.to_dict()
                elif name == 'analyze_statement':
                    from hanni.laya.intelligence import analyze_statement, classify_semantic_status
                    row['semantic_status'] = classify_semantic_status(operation['text'])
                    candidate = analyze_statement(operation['text'], source_ref='controlled_fixture:analysis')
                    row['candidate'] = asdict(candidate) if candidate else None
                    row['input_source'] = operation.get('source', 'owner')
                    row['no_authoritative_writer'] = True
                elif name == 'drop_index':
                    index_name = operation['name']
                    if index_name not in {'idx_memories_updated_at', 'idx_memories_type', 'idx_memories_fact_key', 'idx_memories_project'}:
                        raise ValueError('Unrecognized isolated fixture index')
                    with store._connect() as db:
                        db.execute('DROP INDEX IF EXISTS ' + index_name)
                    with store._connect() as db:
                        row['readback_index_absent'] = index_name not in [value[0] for value in db.execute("SELECT name FROM sqlite_master WHERE type='index'")]
                elif name == 'external_update':
                    with store._connect() as db:
                        db.execute('UPDATE memories SET content=?,normalized_content=? WHERE id=?', (operation['content'], operation['content'].casefold(), labels[operation['target_id']]))
                    row['external_timestamp_retained'] = bool(operation.get('keep_updated_at'))
                elif name == 'tamper' and operation['target'] == 'database_file':
                    if operation['mode'] != 'invalid_bytes':
                        raise ValueError('Unknown owned corruption fixture')
                    store.cleanup()
                    db_path.write_bytes(b'independent controlled invalid SQLite file')
                    row['owned_database_corrupted'] = True
                elif name == 'tamper' and operation['target'] == 'retriever_cache':
                    if operation['mode'] != 'wrong_terms':
                        raise ValueError('Unknown cache corruption fixture')
                    if hasattr(retriever, '_prepared_terms'):
                        retriever._prepared_terms = {'unregistered-fixture-id': ('invalid-revision', {'misleading'})}
                        row['cache_corrupted'] = True
                    else:
                        row['cache_absent'] = True
                else:
                    raise ValueError('Unsupported sealed operation')
            except Exception as exc:
                row['error'] = error(exc)
            row['after'] = snapshot()
            actions.append(row)
        final = retrieve(case['query'], 'final')
        project_started = time.perf_counter()
        project_resolution = None
        if project_context:
            try:
                raw = project_context.resolve(case['query'])
                inverse = {actual: logical for logical, actual in projects.items()}
                project_resolution = {**raw, 'logical_project_id': inverse.get(raw['project_id']), 'logical_candidates': [inverse.get(item['id']) for item in raw['candidates']], 'scope': 'original resolver diagnostic; not automatic native retrieval project selection'}
            except Exception as exc:
                project_resolution = {'error': error(exc)}
        project_ms = (time.perf_counter() - project_started) * 1000
        readbacks = {}
        for logical, actual in labels.items():
            readbacks[logical] = dict(record=safe_call(lambda: store.get(actual).to_dict() if store.get(actual) else None), history=safe_call(lambda: list(store.history(actual))), suggestions=safe_call(lambda: [item.to_dict() for item in store.suggestions() if item.target_id == actual or actual in item.related_ids]))
        if owned_advisory:
            wait_end = time.monotonic() + 0.25
            while owned_advisory._pending and time.monotonic() < wait_end:
                time.sleep(0.002)
        result = dict(id=case['id'], category=case['category'], difficulty=case['difficulty'], linguistic_tags=case.get('linguistic_tags', []), arm=arm, options=options, seed_receipts=seeds, actions=actions, retrievals=retrievals, final=final, project_resolution=project_resolution, project_diagnostic_ms=project_ms, labels=labels, projects=projects, readbacks=readbacks, final_store=snapshot(), fixture_scope='original isolated stores, original retrieval; no owner authority or model inference', effective_retriever_options={key: getattr(retriever, key, None) for key in ('limit', 'max_chars', 'max_tokens', 'min_score', 'project_id')}, actual_model_calls=0, actual_workflow_executions=0, advisory=dict(mode='controlled transport fault' if owned_advisory else 'disabled', fault=case.get('advisory_mode'), calls=fault_opener.calls if fault_opener else [], errors=getattr(owned_advisory, 'errors', None), actual_laya_model_calls=0))
        save(output / 'receipt.json', result)
        return result
    finally:
        if owned_advisory:
            owned_advisory.close()
            owned_advisory._worker.join(2)
            if owned_advisory._worker.is_alive():
                raise RuntimeError('Owned advisory worker did not close')

def run_final(proof_path, output):
    """Requires explicit manager freeze authorization outside this runner."""
    seal = json.loads((PRIVATE / 'holdout/seal.json').read_text(encoding='utf8'))
    for filename, expected in seal['hashes'].items():
        if digest(PRIVATE / 'holdout' / filename) != expected:
            raise RuntimeError('Sealed final inputs changed')
    proof = json.loads(proof_path.read_text(encoding='utf8'))
    if proof['files'] != source_manifest():
        raise RuntimeError('Frozen source does not match')
    claim = PRIVATE / 'holdout-final-claim.json'
    with claim.open('x', encoding='utf8') as stream:
        json.dump(dict(started_at=datetime.now(timezone.utc).isoformat(), output=str(output.resolve()), proof_sha256=digest(proof_path), seal_sha256=digest(PRIVATE / 'holdout/seal.json'), status='once_only_started'), stream, indent=2)
    cases = [json.loads(line) for line in (PRIVATE / 'holdout/cases.jsonl').read_text(encoding='utf8').splitlines()]
    output.mkdir(parents=True, exist_ok=False)
    completed = []
    for arm in ('legacy', 'context'):
        for case in cases:
            if source_manifest() != proof['files']:
                save(output / 'ABORT.json', dict(reason='source_changed', completed=completed))
                raise RuntimeError('Frozen source changed; remaining cases not tested')
            destination = output / 'receipts' / arm / case['id']
            try:
                receipt = run_case(case, destination, arm)
                state = 'executed'
            except Exception as exc:
                state = 'fixture_or_execution_error'
                save(destination / 'receipt.json', dict(id=case['id'], arm=arm, category=case['category'], error=dict(type=type(exc).__name__, message=str(exc)), status=state))
            completed.append(dict(id=case['id'], arm=arm, status=state, receipt_sha256=digest(destination / 'receipt.json')))
            save(output / 'PROGRESS.json', dict(completed=completed, planned=len(cases) * 2))
            print(json.dumps(dict(arm=arm, completed=len(completed), planned=len(cases) * 2, state=state)), flush=True)
    save(output / 'COMPLETE.json', dict(completed=completed, source_unchanged=source_manifest() == proof['files']))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['snapshot', 'final'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--proof', type=Path)
    args = parser.parse_args()
    if args.operation == 'snapshot':
        proof = freeze(args.output)
        print(json.dumps(dict(files=len(proof['files']), archive_sha256=proof['archive_sha256'])))
    else:
        if args.proof is None:
            parser.error('final requires --proof')
        run_final(args.proof, args.output)

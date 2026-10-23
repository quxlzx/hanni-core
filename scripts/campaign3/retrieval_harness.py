"""Isolated original SQLite memory/retrieval campaign runner.

Expected IDs are author labels, independently assigned before execution. The
runner maps them to actual original-store IDs and never replaces retrieval.
Project diagnostics and controlled advisory faults have separate provenance.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
import inspect
from hanni.memory.store import MemoryStore
from hanni.memory.retrieval import LocalMemoryRetriever, ContextAwareRetriever
ROOT = Path(__file__).resolve().parents[2]

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

class FaultOpener:
    """Original advisory HTTP boundary, immediate controlled failure only."""

    def __init__(self, mode):
        self.mode, self.calls = (mode, [])

    def open(self, request, timeout):
        self.calls.append({'timeout': timeout, 'body_sha256': hashlib.sha256(request.data).hexdigest()})
        if self.mode == 'timeout':
            raise TimeoutError('synthetic bounded advisory timeout')
        if self.mode == 'disconnect':
            raise ConnectionRefusedError('synthetic advisory disconnection')
        if self.mode == 'invalid_json':
            return self.Response(b'not-json')
        if self.mode == 'oversized':
            return self.Response(b'X' * 70000)
        raise OSError('synthetic advisory dependency unavailable')

    class Response:
        status = 200

        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, length):
            return self.value[:length]

def score_receipt(receipt, expected):
    """Report fixed-K and returned-set precision with explicit denominators."""
    relevant, forbidden = (set(expected.get('relevant_ids', [])), set(expected.get('excluded_ids', [])))
    observed = receipt.get('logical_ids', [])[:5]
    hits = len(relevant.intersection(observed))
    output = {'relevant_count': len(relevant), 'returned_count': len(observed), 'hits': hits, 'recall_at_5': hits / len(relevant) if relevant else None, 'precision_at_5_fixed_denominator': hits / 5, 'precision_returned_at_5': hits / len(observed) if observed else None, 'forbidden_ids': sorted(forbidden.intersection(observed)), 'irrelevant_ids': sorted(set(observed) - relevant - set(expected.get('allowed_ids', []))), 'negative_abstention': not observed if not relevant else None}
    checks = []

    def check(label, passed, actual, wanted):
        checks.append({'check': label, 'passed': bool(passed), 'observed': actual, 'expected': wanted})
    allowed_errors = expected.get('allowed_error_types', [])
    if receipt.get('error'):
        check('original dependency error classification', receipt['error']['type'] in allowed_errors, receipt['error']['type'], allowed_errors)
    else:
        check('relevant IDs recalled', relevant.issubset(observed), observed, sorted(relevant))
        check('excluded IDs absent', not output['forbidden_ids'], output['forbidden_ids'], [])
        if not expected.get('allow_irrelevant', False):
            check('unrelated IDs absent', not output['irrelevant_ids'], output['irrelevant_ids'], [])
        if not relevant and expected.get('expect_empty', True):
            check('negative query stays empty', not observed, observed, [])
    if 'max_context_utf8_bytes' in expected:
        actual = len(receipt.get('context_text', '').encode('utf-8'))
        check('whole context byte budget', actual <= expected['max_context_utf8_bytes'], actual, expected['max_context_utf8_bytes'])
    for fragment in expected.get('forbidden_context_fragments', []):
        check('unsafe fragment omitted', fragment not in receipt.get('context_text', ''), fragment, False)
    for field in ('source_by_id', 'source_ref_by_id', 'status_by_id', 'content_by_id'):
        actual_field = {'source_by_id': 'source', 'source_ref_by_id': 'source_ref', 'status_by_id': 'semantic_status', 'content_by_id': 'content'}[field]
        by_id = {row['logical_id']: row for row in receipt.get('records', [])}
        for label, wanted in expected.get(field, {}).items():
            actual = by_id.get(label, {}).get(actual_field)
            check(f'{actual_field} provenance for {label}', actual == wanted, actual, wanted)
    resolution = receipt.get('project_resolution', {})
    for key in ('project_status', 'project_id'):
        if key in expected:
            actual = resolution.get('status' if key == 'project_status' else 'logical_project_id')
            check(key, actual == expected[key], actual, expected[key])
    output.update(checks=checks, passed=all((row['passed'] for row in checks)))
    return output

def run_case(case, db_path, retriever_kind='legacy', config=None, advisory=None):
    """Run an independent JSON case using original memory APIs, in isolation.

    Supported actions: retrieve, correct, delete, restart, touch, drop_index,
    external_update, tamper (fixed metadata/content columns), analyze_statement,
    remember, corrupt_database. Per-action expected/error metadata never changes
    production behavior. All logical/project/source identities are retained.
    """
    if retriever_kind not in {'legacy', 'context'}:
        raise ValueError('unknown retriever kind')
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        raise ValueError('run_case requires a new isolated database path')
    store = MemoryStore(db_path, max_item_chars=case.get('max_item_chars', 1200))
    labels, project_ids, actions, contexts, setup_errors = ({}, {}, [], [], [])
    settings = {'limit': 5, 'max_chars': 4000, 'max_tokens': 4000, 'min_score': 25.0}
    settings.update(case.get('options', {}))
    opener, owned_advisory, project_context = (None, None, None)
    import hanni.memory.store, hanni.memory.retrieval, hanni.memory.privacy, hanni.memory.facts
    import hanni.memory.projects, hanni.laya.intelligence, hanni.laya.advisory, hanni.dashboard.productivity
    original_modules = (hanni.memory.store, hanni.memory.retrieval, hanni.memory.privacy, hanni.memory.facts, hanni.memory.projects, hanni.laya.intelligence, hanni.laya.advisory, hanni.dashboard.productivity)
    original_hashes = {module.__name__: hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest() for module in original_modules}
    original_import_paths = {module.__name__: str(Path(inspect.getfile(module)).resolve()) for module in original_modules}
    if advisory is None and case.get('advisory_mode'):
        from hanni.laya.advisory import AdvisoryClient
        opener = FaultOpener(case['advisory_mode'])
        owned_advisory = AdvisoryClient(enabled=True, retrieval_enabled=True, quality_gate_passed=True, token='synthetic-campaign3-advisory-authorization-only', allow_stored_memories=True, timeout_seconds=0.05, opener=opener)
        advisory = owned_advisory

    def error(exc):
        return {'type': type(exc).__name__, 'message': str(exc)}

    def snapshot():
        try:
            return [record.to_dict() for record in store.iter_records()]
        except Exception as exc:
            return {'error': error(exc)}

    def storage_diagnostics():
        try:
            with store._connect() as db:
                return {'indexes': [dict(row) for row in db.execute('PRAGMA index_list(memories)')], 'schema_version': db.execute("SELECT value FROM memory_meta WHERE key='schema_version'").fetchone()[0]}
        except Exception as exc:
            return {'error': error(exc)}

    def new_retriever():
        options = {key: settings[key] for key in ('limit', 'max_chars', 'min_score')}
        scope = project_ids.get(case.get('project_id', ''), case.get('project_id', ''))
        if retriever_kind == 'legacy':
            accepted = inspect.signature(LocalMemoryRetriever).parameters
            for key, value in (('max_tokens', settings['max_tokens']), ('project_id', scope)):
                if key in accepted:
                    options[key] = value
            return LocalMemoryRetriever(store, **options)
        return ContextAwareRetriever(store, max_tokens=settings['max_tokens'], project_id=scope, advisory=advisory, **options)

    def remember(item):
        metadata = {key: item[key] for key in ('source', 'confidence', 'memory_type', 'semantic_status', 'source_ref') if key in item}
        metadata['project_id'] = project_ids.get(item.get('project_id', ''), item.get('project_id', ''))
        metadata.setdefault('source_ref', 'synthetic:' + case['id'] + ':' + item['id'])
        if item.get('raw_import'):
            actual_id = uuid.uuid4().hex
            now = '2025-01-01T00:00:00+00:00'
            with store._connect() as db:
                db.execute('INSERT INTO memories(id,content,normalized_content,memory_type,source,confidence,created_at,updated_at,fact_key,fact_value,project_id,semantic_status,source_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (actual_id, item['content'], item['content'].casefold(), item.get('memory_type', 'fact'), item.get('source', 'synthetic_import'), item.get('confidence', 1.0), now, now, item.get('fact_key', ''), item.get('fact_value', ''), metadata['project_id'], item.get('semantic_status', 'statement'), metadata['source_ref']))
            record, created = (store.get(actual_id), True)
        else:
            record, created = store.remember(item['content'], **metadata)
        labels[item['id']] = record.id
        actions.append({'op': 'remember', 'logical_id': item['id'], 'actual_id': record.id, 'created': created, 'record': record.to_dict(), 'raw_import_fixture': bool(item.get('raw_import'))})
        if item.get('expect_rejection'):
            setup_errors.append({'op': 'remember', 'logical_id': item['id'], 'error': {'type': 'ExpectedRejectionMissing', 'message': 'Original store accepted a prospectively forbidden write.'}})
    try:
        if case.get('projects'):
            from hanni.dashboard.productivity import ProductivityStore
            from hanni.memory.projects import ProjectContext
            workspace = ProductivityStore(db_path.parent / 'workspace')
            workflows = {row.get('workflow_id', row.get('id')): row for row in case.get('workflows', [])}

            def workflow_reader(identity):
                actions.append({'op': 'controlled_workflow_read', 'workflow_id': identity, 'scope': 'synthetic ledger dependency'})
                if identity not in workflows:
                    raise ValueError('synthetic workflow missing')
                return {'workflow': workflows[identity]}
            project_context = ProjectContext(store, workspace, workflow_reader if workflows else None)
            for item in case['projects']:
                result = workspace.mutate('project.create', {'name': item['name'], 'description': item.get('description', '')}, str(uuid.uuid4()))['project']
                project_ids[item['id']] = result['id']
                for alias in item.get('aliases', []):
                    project_context.add_alias(result['id'], alias, expected_fingerprint=result['fingerprint'])
            for link in case.get('links', []):
                actual = project_ids[link['project_id']]
                project = project_context.project(actual)
                project_context.link_workflow(actual, link['workflow_id'], expected_fingerprint=project['fingerprint'])
        for item in case.get('memories', []):
            try:
                remember(item)
            except Exception as exc:
                rejected = {'op': 'remember', 'logical_id': item['id'], 'error': error(exc)}
                rejected['expected_rejection'] = bool(item.get('expect_rejection'))
                actions.append(rejected)
                if not item.get('expect_rejection'):
                    setup_errors.append(rejected)
        before = snapshot()
        storage_before = storage_diagnostics()
        retriever = new_retriever()

        def retrieve(query, expected):
            started = time.perf_counter()
            receipt = {'query': query, 'retriever_kind': retriever_kind, 'expected': expected, 'scope_input': case.get('project_id', ''), 'scope_provenance': 'explicit fixture input, not inferred project selection'}
            receipt['effective_limits'] = {key: getattr(retriever, key, None) for key in ('limit', 'max_chars', 'max_tokens', 'min_score', 'project_id')}
            receipt['cache_before_ids'] = list(getattr(retriever, '_prepared_terms', {}))
            try:
                excluded = tuple((labels.get(label, label) for label in case.get('exclude_ids', [])))
                context = retriever.retrieve(query, exclude_ids=excluded)
                reverse = {actual: label for label, actual in labels.items()}
                records = [{**match.record.to_dict(), 'logical_id': reverse.get(match.record.id, match.record.id), 'score': match.score, 'score_kind': 'uncalibrated retrieval heuristic'} for match in context.matches]
                receipt.update(context_text=context.text, records=records, actual_ids=[row['id'] for row in records], logical_ids=[row['logical_id'] for row in records], context_chars=len(context.text), context_utf8_token_upper_bound=len(context.text.encode('utf-8')), token_measurement='UTF-8 byte upper bound; no tokenizer claim', production_metrics=dict(getattr(retriever, 'last_metrics', {})))
            except Exception as exc:
                receipt.update(error=error(exc), logical_ids=[], records=[], context_text='')
            receipt['retrieval_ms'] = round((time.perf_counter() - started) * 1000, 4)
            receipt['cache_after_ids'] = list(getattr(retriever, '_prepared_terms', {}))
            diagnostics_started = time.perf_counter()
            if project_context is not None:
                try:
                    resolution = project_context.resolve(query)
                    inverse = {actual: logical for logical, actual in project_ids.items()}
                    receipt['project_resolution'] = {**resolution, 'logical_project_id': inverse.get(resolution['project_id']), 'scope': 'original resolver diagnostic; not a native legacy retrieval path'}
                    if resolution['status'] == 'matched':
                        receipt['project_package_diagnostic'] = project_context.package(resolution['project_id'], max_chars=min(12000, max(500, settings['max_chars'])), max_records=settings['limit'])
                except Exception as exc:
                    receipt['project_resolution'] = {'error': error(exc)}
            receipt['project_diagnostic_ms'] = round((time.perf_counter() - diagnostics_started) * 1000, 4)
            receipt['total_retrieve_diagnostic_ms'] = round((time.perf_counter() - started) * 1000, 4)
            receipt['scores'] = score_receipt(receipt, expected)
            contexts.append(receipt)
            return receipt
        for operation in case.get('operations', []):
            row = {'op': operation['op'], 'before': snapshot(), 'storage_before': storage_diagnostics()}
            row['fingerprint_before'] = None
            try:
                row['fingerprint_before'] = store.fingerprint()
            except Exception:
                pass
            try:
                name = operation['op']
                if name == 'retrieve':
                    row['context_index'] = len(contexts)
                    retrieve(operation.get('query', case['query']), operation.get('expected', case.get('expected', {})))
                elif name == 'remember':
                    item = dict(operation['memory'])
                    item.pop('expect_rejection', None)
                    remember(item)
                elif name == 'restart':
                    store = MemoryStore(db_path, max_item_chars=store.max_item_chars)
                    retriever = new_retriever()
                elif name == 'correct':
                    record = store.get(labels[operation['target_id']])
                    metadata = {key: operation[key] for key in ('source', 'semantic_status', 'source_ref') if key in operation}
                    if 'project_id' in operation:
                        metadata['project_id'] = project_ids.get(operation['project_id'], operation['project_id'])
                    changed = store.correct(record.id, operation['content'], expected_updated_at=operation.get('expected_updated_at', record.updated_at.isoformat()), **metadata)
                    row['result'] = changed.to_dict()
                elif name == 'delete':
                    row['deleted'] = store.delete(labels[operation['target_id']])
                elif name in {'touch', 'external_update', 'tamper'}:
                    allowed = {'content', 'normalized_content', 'source', 'source_ref', 'semantic_status', 'project_id', 'fact_key', 'fact_value', 'updated_at', 'created_at', 'confidence'}
                    updates = operation.get('fields', {})
                    if name == 'touch':
                        updates = {'updated_at': operation.get('updated_at', '2000-01-01T00:00:00+00:00')}
                    if not updates or set(updates) - allowed:
                        raise ValueError('unsupported fixed import-fixture columns')
                    with store._connect() as db:
                        db.execute('UPDATE memories SET ' + ','.join((key + '=?' for key in updates)) + ' WHERE id=?', (*updates.values(), labels[operation['target_id']]))
                elif name == 'drop_index':
                    index = operation.get('index', 'idx_memories_type')
                    if index not in {'idx_memories_type', 'idx_memories_updated_at', 'idx_memories_fact_key', 'idx_memories_project'}:
                        raise ValueError('unsupported fixture index')
                    with store._connect() as db:
                        db.execute('DROP INDEX IF EXISTS ' + index)
                elif name == 'analyze_statement':
                    from hanni.laya.intelligence import analyze_statement, classify_semantic_status
                    row['semantic_status'] = classify_semantic_status(operation['text'])
                    candidate = analyze_statement(operation['text'], source_ref=operation.get('source_ref', 'synthetic:analysis'))
                    row['candidate'] = asdict(candidate) if candidate else None
                    if 'expected_status' in operation:
                        row['assertion_status'] = row['semantic_status'] == operation['expected_status']
                    if 'expected_candidate' in operation:
                        row['assertion_candidate'] = (candidate is not None) == operation['expected_candidate']
                elif name == 'corrupt_database':
                    store.cleanup()
                    db_path.write_bytes(b'synthetic deliberately invalid SQLite data')
                else:
                    raise ValueError('unsupported scenario operation')
            except Exception as exc:
                row['error'] = error(exc)
            row['after'] = snapshot()
            row['storage_after'] = storage_diagnostics()
            try:
                row['fingerprint_after'] = store.fingerprint()
            except Exception as exc:
                row['fingerprint_after_error'] = error(exc)
            allowed_errors = operation.get('allowed_error_types', operation.get('expected', {}).get('allowed_error_types', []))
            expects_error = bool(operation.get('expect_rejection') or operation.get('expect_error'))
            if row.get('error'):
                row['assertion_error'] = bool(expects_error or row['error']['type'] in allowed_errors)
                if allowed_errors:
                    row['assertion_error'] = row['error']['type'] in allowed_errors
            else:
                row['assertion_error'] = not expects_error
            if 'expect_fingerprint_change' in operation:
                changed = row.get('fingerprint_before') != row.get('fingerprint_after')
                row['assertion_fingerprint'] = changed == operation['expect_fingerprint_change']
            if 'expected_deleted' in operation:
                row['assertion_deleted'] = row.get('deleted') == operation['expected_deleted']
            actions.append(row)
        if case.get('query') is not None:
            retrieve(case['query'], case.get('expected', {}))
        if owned_advisory is not None:
            deadline = time.monotonic() + 0.2
            while time.monotonic() < deadline and owned_advisory._pending:
                time.sleep(0.002)
        result = {'id': case['id'], 'category': case['category'], 'difficulty': case.get('difficulty', 'medium'), 'retriever_kind': retriever_kind, 'source_hashes': original_hashes, 'source_import_paths': original_import_paths, 'before': before, 'after': snapshot(), 'storage_before': storage_before, 'storage_after': storage_diagnostics(), 'logical_to_actual': labels, 'logical_projects': project_ids, 'actions': actions, 'contexts': contexts, 'setup_errors': setup_errors, 'advisory': {'mode': 'controlled original-client dependency fault' if opener else 'supplied optional advisory' if advisory else 'disabled', 'fault': case.get('advisory_mode'), 'calls': opener.calls if opener else [], 'errors': getattr(advisory, 'errors', None), 'status': getattr(advisory, 'status', None)}, 'passed': not setup_errors and all((row['scores']['passed'] for row in contexts)) and all((all((value for key, value in row.items() if key.startswith('assertion_'))) for row in actions))}
        return result
    finally:
        if owned_advisory is not None:
            owned_advisory.close()
            if owned_advisory._worker is not None:
                owned_advisory._worker.join(timeout=1)

def setup_store(case, db_path, retriever_kind='legacy'):
    """Apply the same original-store scenario and return its final isolated DB.

    This is setup for the manager's real-model A/B, never a model answer source.
    The supplied case's ground truth remains independent of returned contents.
    Corrupted/unavailable stores raise honestly when the manager opens them.
    """
    receipt = run_case(case, db_path, retriever_kind)
    return (MemoryStore(Path(db_path), max_item_chars=case.get('max_item_chars', 1200)), receipt)

def run_corpus(path, output, kinds=('legacy', 'context')):
    cases = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    corpus_hash = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    all_results = []
    for kind in kinds:
        results = []
        for case in cases:
            try:
                receipt = run_case(case, output / 'stores' / kind / case['id'] / 'memory.sqlite', kind)
            except Exception as exc:
                receipt = {'id': case['id'], 'category': case['category'], 'retriever_kind': kind, 'passed': False, 'harness_error': {'type': type(exc).__name__, 'message': str(exc)}}
            save(output / 'receipts' / kind / (case['id'] + '.json'), receipt)
            results.append(receipt)
        all_results.extend(results)
        summary = {'retriever_kind': kind, 'corpus_sha256': corpus_hash, 'cases': len(results), 'passed': sum((row['passed'] for row in results)), 'failed': sum((not row['passed'] for row in results))}
        for category in dict.fromkeys((row['category'] for row in results)):
            rows = [row for row in results if row['category'] == category]
            summary.setdefault('categories', {})[category] = {'cases': len(rows), 'passed': sum((row['passed'] for row in rows))}
        save(output / (kind + '-summary.json'), summary)
        print(json.dumps(summary), flush=True)
    return all_results
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run_corpus(args.corpus, args.output)

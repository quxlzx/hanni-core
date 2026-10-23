"""Isolated, guarded actual-model diagnostics, never simulated LAYA answers."""
from __future__ import annotations
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import psutil
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession, system_prompt_for
from hanni.memory.retrieval import ContextAwareRetriever, LocalMemoryRetriever
from hanni.memory.session import MemoryAwareSession
from hanni.memory.store import MemoryStore
from hanni.models.adaptive import AdaptiveModelEngine, model_request_scope
from hanni.models.client import LlamaCppClient
from hanni.reliability.execution import close_service
from scripts.campaign1_verification.recording import Recording, hooks, record_into

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf8')

def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def source_manifest():
    paths = list((ROOT / 'src/hanni/memory').glob('*.py'))
    paths += list((ROOT / 'src/hanni/laya').glob('*.py'))
    paths += [ROOT / 'src/hanni/models/adaptive.py', ROOT / 'src/hanni/models/client.py', ROOT / 'src/hanni/core/orchestrator.py', ROOT / 'config/hanni.yaml', ROOT / 'config/models.yaml', Path(__file__)]
    return {str(path.relative_to(ROOT)): digest_file(path) for path in sorted(paths)}

def runtime_snapshot(config):
    """Inspect listener identity and whitelisted flags, never memory contents."""
    spec = config.models.supervisor
    ports = {urlsplit(spec.endpoint).port, 8765, 8766}
    listeners = [row for row in psutil.net_connections(kind='tcp') if row.status == psutil.CONN_LISTEN and row.laddr.port in ports]
    evidence = {'captured_at': datetime.now(timezone.utc).isoformat(), 'available_ram_bytes': psutil.virtual_memory().available, 'listeners': sorted({(row.laddr.port, row.pid) for row in listeners}), 'memory_config': {'context_enabled': config.hanni.memory.context_enabled, 'retrieval_enabled': config.hanni.memory.retrieval_enabled}, 'laya_config': {'advisory_enabled': config.hanni.laya.advisory_enabled, 'retrieval_enabled': config.hanni.laya.retrieval_enabled, 'allow_stored_memories': config.hanni.laya.allow_stored_memories}, 'model_generation_defaults': {'temperature': spec.temperature, 'top_p': spec.top_p, 'max_tokens': spec.max_tokens}, 'scope': 'Read-only identity and flags; owner memory stores not opened.'}
    health = LlamaCppClient(spec).health()
    evidence['original_client_health'] = {'ok': health.ok, 'detail': health.detail}
    pids = {row.pid for row in listeners if row.laddr.port == urlsplit(spec.endpoint).port and row.pid}
    if len(pids) == 1:
        process = psutil.Process(next(iter(pids)))
        command = process.cmdline()
        model = None
        for flag in ('-m', '--model'):
            if flag in command:
                model = Path(command[command.index(flag) + 1])
                break
        if model is None:
            mapped = {Path(row.path) for row in process.memory_maps() if row.path.casefold().endswith('.gguf')}
            if len(mapped) == 1:
                model = mapped.pop()
        evidence['model_process'] = {'pid': process.pid, 'create_time': process.create_time(), 'command_sha256': hashlib.sha256(json.dumps(command).encode()).hexdigest()}
        if model is not None and model.is_file():
            evidence['model_process'].update(model_file=model.name, model_bytes=model.stat().st_size, model_sha256=digest_file(model))
        parent = process.parent()
        if parent is not None:
            evidence['parent_process'] = {'pid': parent.pid, 'create_time': parent.create_time()}
            try:
                environment = parent.environ()
                keys = ('HANNI_LAYA_SHADOW_ENABLED', 'HANNI_LAYA_TRANSPORT', 'HANNI_LAYA_ALLOW_REMOTE_TEXT')
                evidence['parent_laya_flags'] = {key: environment.get(key) for key in keys}
            except (psutil.Error, NotImplementedError) as exc:
                evidence['parent_laya_flags_unavailable'] = type(exc).__name__
    return evidence

def tokenizer_measurement(spec, context, messages, empty_messages):
    """Actual installed tokenizer endpoints; no inference or admission bypass."""
    base = spec.endpoint.rstrip('/').removesuffix('/v1')
    if urlsplit(base).hostname not in {'127.0.0.1', 'localhost'}:
        raise ValueError('Only the existing loopback tokenizer may be inspected')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    receipts = []

    def post(path, payload):
        request = urllib.request.Request(base + path, data=json.dumps(payload).encode('utf8'), method='POST', headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=3) as response:
            result = json.load(response)
        receipts.append({'endpoint_path': path, 'payload': payload, 'response': result})
        return result

    def count(content):
        tokens = post('/tokenize', {'content': content, 'add_special': False, 'parse_special': True})['tokens']
        if not isinstance(tokens, list) or any((type(token) is not int for token in tokens)):
            raise ValueError('Invalid tokenizer output')
        return len(tokens)

    def formatted_count(rows):
        prompt = post('/apply-template', {'messages': rows, 'chat_template_kwargs': {'enable_thinking': spec.thinking_enabled}})['prompt']
        return count(prompt)
    full, empty = (formatted_count(messages), formatted_count(empty_messages))
    return {'context_tokens': count(context), 'full_formatted_prompt_tokens': full, 'empty_memory_prompt_tokens': empty, 'memory_prompt_delta_tokens': full - empty, 'native_api_receipts': receipts, 'scope': 'Native tokenizer counts; no model generation or server usage claim.'}

class CapturingClient:

    def __init__(self, client):
        self.client = client
        self.messages = []

    def stream_chat(self, messages, **options):
        self.messages = [dict(row) for row in messages]
        with model_request_scope(task_category='memory', local_only=True, privacy_categories=frozenset({'conversation', 'memory', 'sensitive'}), allow_legacy_default=True):
            yield from self.client.stream_chat(messages, **options)

def guarded_case(case, arm, config, engine, client, output):
    if 'query' in case:
        from scripts.campaign3.retrieval_harness import setup_store
        store, setup_receipt = setup_store(case, output / 'state' / 'memory.sqlite3', 'legacy' if arm == 'A' else 'context')
        prompt = case['query']
        save(output / 'SETUP.json', setup_receipt)
    else:
        store = MemoryStore(output / 'state' / 'memory.sqlite3')
        for index, content in enumerate(case['memories']):
            store.remember(content, source='owner_explicit:synthetic_campaign3', source_ref=f"campaign3:{case['id']}:{index}")
        prompt = case['prompt']
        setup_receipt = None
    capture = CapturingClient(client)
    fallback = TextSession(capture, system_prompt=system_prompt_for(config.hanni.personality))
    options = {'limit': 5, 'max_chars': 4000, 'min_score': 25.0}
    options.update({key: value for key, value in case.get('options', {}).items() if key in options})
    project_id = ''
    if setup_receipt is not None:
        project_id = setup_receipt['logical_projects'].get(case.get('project_id'), '')
    profile = dict(options, project_id=project_id, max_tokens=case.get('options', {}).get('max_tokens', 4000))
    retriever = LocalMemoryRetriever(store, **profile) if arm == 'A' else ContextAwareRetriever(store, **profile)
    context = retriever.retrieve(prompt)
    empty_messages = fallback.build_messages(prompt)
    session = MemoryAwareSession(fallback, store, extraction_enabled=False, context_retriever=retriever)
    before = store.fingerprint()
    recording = Recording(lambda event: None)
    receipt = {'id': case['id'], 'arm': arm, 'prompt': prompt, 'scope': 'Original isolated MemoryAwareSession/TextSession and guarded local transport; no tools.', 'laya_model_used': False, 'retrieved_ids': [row.record.id for row in context.matches], 'category': case.get('category'), 'answer_oracle': case.get('model_probe'), 'context_project_scope': {'project_id': project_id, 'scope': 'Explicit isolated fixture scope, not model or native project identification.'}, 'effective_limits': {key: getattr(retriever, key) for key in ('limit', 'max_chars', 'max_tokens', 'min_score', 'project_id')}, 'context_utf8_byte_upper_bound': len(context.text.encode('utf8')), 'exact_context_tokens': None, 'requested_evaluation_options': {'temperature': 0.0, 'top_p': 1.0, 'max_tokens': 256}, 'resource_before': {'available_ram_bytes': psutil.virtual_memory().available}}
    started = time.perf_counter()
    try:
        with record_into(recording):
            receipt['answer'] = ''.join(session.stream_response(prompt, temperature=0.0, top_p=1.0, max_tokens=256))
        receipt['native_memory_request_ms'] = (time.perf_counter() - started) * 1000
        receipt['status'] = 'unscored_actual_response'
    except Exception as exc:
        receipt['native_memory_request_ms'] = (time.perf_counter() - started) * 1000
        receipt.update(status='blocked', error={'type': type(exc).__name__, 'message': str(exc)})
        if type(exc).__name__ == 'ModelSelectionError':
            inspection_started = time.perf_counter()
            with model_request_scope(task_category='memory', local_only=True, privacy_categories=frozenset({'conversation', 'memory', 'sensitive'}), allow_legacy_default=True):
                request = client._request({'max_tokens': 256})
            inspected = engine.select(replace(request, context_tokens=len(json.dumps(capture.messages, ensure_ascii=False).encode('utf8'))))
            receipt['separate_original_admission_inspection'] = {'excluded': inspected['excluded'], 'reason': inspected['reason'], 'duration_ms': (time.perf_counter() - inspection_started) * 1000, 'scope': 'Separate original selector inspection after refusal, not a model response.'}
    receipt.update(attempt_plus_admission_inspection_ms=(time.perf_counter() - started) * 1000, messages=capture.messages, calls=recording.calls, actual_model_http_requests=sum((len(row['http_attempts']) for row in recording.calls)), store_unchanged=before == store.fingerprint())
    try:
        if capture.messages:
            injected = capture.messages[-2]['content'] if len(capture.messages) == 3 else ''
            receipt['pre_session_context_matches_injected'] = context.text == injected
            receipt['injected_context_utf8_byte_upper_bound'] = len(injected.encode('utf8'))
            receipt['tokenizer_measurement'] = tokenizer_measurement(config.models.supervisor, injected, capture.messages, empty_messages)
            receipt['exact_context_tokens'] = receipt['tokenizer_measurement']['context_tokens']
    except Exception as exc:
        receipt['tokenizer_measurement'] = {'error': type(exc).__name__ + ': ' + str(exc)}
    if not receipt['actual_model_http_requests']:
        if 'error' in receipt:
            receipt['status'] = 'blocked'
            receipt['answer'] = None
        else:
            receipt['status'] = 'deterministic_no_model_response'
    elif 'error' in receipt:
        receipt['status'] = 'failed_actual_inference'
    save(output / 'receipt.json', receipt)
    return receipt

def run(output, *, cases=None, identify=True):
    cases = cases or [{'id': 'guarded-diagnostic-1', 'memories': ['For the Lucent calendar review, I selected Markdown tables.'], 'prompt': 'Which document format did I select for the Lucent calendar review?'}]
    rows = []
    prepared = {'started_at': datetime.now(timezone.utc).isoformat(), 'source_before': source_manifest(), 'scope': 'Synthetic isolated memories; no owner data/config/process mutation.'}
    save(output / 'PREPARED.json', prepared)
    with tempfile.TemporaryDirectory(prefix='hanni-campaign3-model-') as folder, hooks():
        config = load_config(ROOT / 'config', data_dir=Path(folder) / 'state', env={})
        if identify:
            save(output / 'RUNTIME_IDENTITY.json', runtime_snapshot(config))
        config = replace(config, hanni=replace(config.hanni, model_routing=replace(config.hanni.model_routing, max_fallbacks=0)))
        engine = AdaptiveModelEngine(config)
        client = engine.wrap_client(LlamaCppClient(config.models.supervisor, max_attempts=1))
        try:
            for case in cases:
                for arm in ('A', 'D'):
                    row = guarded_case(case, arm, config, engine, client, output / case['id'] / arm)
                    rows.append(row)
                    print(json.dumps({'id': case['id'], 'arm': arm, 'status': row['status'], 'http_requests': row['actual_model_http_requests']}), flush=True)
        finally:
            engine.close()
            close_service(Path(folder) / 'state')
    summary = {'attempts': len(rows), 'actual_model_http_requests': sum((row['actual_model_http_requests'] for row in rows)), 'blocked': sum((row['status'] == 'blocked' for row in rows)), 'deterministic_no_model_responses': sum((row['status'] == 'deterministic_no_model_response' for row in rows)), 'all_stores_unchanged': all((row['store_unchanged'] for row in rows)), 'A': 'Configured legacy retrieval, no LAYA', 'D': 'Optional deterministic context retrieval, no LAYA', 'B': {'status': 'unavailable', 'actual_laya_model_calls': 0, 'reason': 'LAYA advisory/retrieval is disabled and independent production gate is closed.'}, 'response_accuracy': None, 'incorrect_memory_claims': None, 'scope': 'Admission diagnostics; unscored actual answers require independent verification.'}
    prepared.update(finished_at=datetime.now(timezone.utc).isoformat(), source_after=source_manifest())
    prepared['source_unchanged'] = prepared['source_before'] == prepared['source_after']
    save(output / 'RUN_METADATA.json', prepared)
    save(output / 'SUMMARY.json', summary)
    print(json.dumps(summary), flush=True)
    return summary

def select_development_cases(path, count):
    """Before output, choose a deterministic round-robin category diagnostic."""
    from hanni.memory.session import _QUERY_RE, _LIST_RE, _REMEMBER_RE, _FORGET_RE
    from hanni.memory.facts import project_reference
    if count < 1:
        raise ValueError('Diagnostic case count must be positive')
    cases = [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]
    groups = {}
    for case in cases:
        if not case.get('model_probe') or not case.get('query'):
            continue
        if any((pattern.match(case['query']) for pattern in (_QUERY_RE, _LIST_RE, _REMEMBER_RE, _FORGET_RE))):
            continue
        if project_reference(case['query']):
            continue
        groups.setdefault(case['category'], []).append(case)
    selected = []
    while groups and len(selected) < count:
        for category in list(groups):
            selected.append(groups[category].pop(0))
            if not groups[category]:
                del groups[category]
            if len(selected) == count:
                break
    if not selected:
        raise ValueError('No eligible development model diagnostics were found')
    return selected
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-identity', action='store_true')
    parser.add_argument('--development-corpus', type=Path)
    parser.add_argument('--cases', type=int, default=20)
    args = parser.parse_args()
    cases = select_development_cases(args.development_corpus, args.cases) if args.development_corpus else None
    if cases is not None:
        save(args.output / 'SELECTED_DEVELOPMENT.json', {'selection_before_inference': True, 'corpus_sha256': digest_file(args.development_corpus), 'cases': [case['id'] for case in cases], 'categories': sorted({case['category'] for case in cases}), 'scope': 'Development model diagnostics; no private holdout use.'})
    run(args.output, cases=cases, identify=not args.no_identity)

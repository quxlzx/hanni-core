"""Reproduce Phase 1 routing and local end-to-end text measurements.

No model downloads, service lifecycle, remote inference, owner memory, or action
execution. Use --source-root data/phase1/baseline/src for the captured baseline.
Live means actual loopback model plus actual allowlisted read handlers. Routing
checks use a metadata-only registry with synthetic Google scope, never handlers.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import platform
from pathlib import Path
import re
import sys
import tempfile
import time
from unittest.mock import patch


def sentences(text):
    # Do not count decimal points, drive paths or initials as sentence ends.
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text.strip()) if s.strip()]


def percentiles(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {'n': 0, 'p50': None, 'p95': None}
    def percentile(p):
        i = (len(values) - 1) * p
        a = int(i)
        return values[a] + (values[min(a + 1, len(values) - 1)] - values[a]) * (i - a)
    return {'n': len(values), 'p50': percentile(.5), 'p95': percentile(.95)}


def independently_valid(name, data):
    """Separate evaluator predicates; do not reuse Hanni's verification code."""
    if not isinstance(data, dict) or not data:
        return False
    if name == 'system.stats':
        return all(type(data.get(k)) in (int, float) and math.isfinite(data[k]) and 0 <= data[k] <= 100
                   for k in ('cpu_percent', 'ram_percent'))
    if name == 'time.now':
        return type(data.get('epoch')) in (int, float) and abs(data['epoch'] - time.time()) < 30
    if name.startswith('process.top_'):
        rows = data.get('processes', [])
        field = 'cpu_percent' if name.endswith('cpu') else 'rss_mb'
        return bool(rows) and all(isinstance(r, dict) and isinstance(r.get('name'), str)
                                 and type(r.get(field)) in (int, float) and r[field] >= 0 for r in rows)
    if name == 'system.info':
        # Full fields vary by platform. Reject an empty purported machine snapshot.
        return len(data) >= 3 and any(k in data for k in ('os', 'platform', 'cpu_count', 'logical_cpus'))
    if name in {'disk.usage', 'disk.free_space'}:
        return bool(data.get('drives') or data.get('disks') or data.get('free_gb') is not None
                    or data.get('free_bytes') is not None or data.get('volumes'))
    return False


def evidence_in_answer(name, data, answer):
    if name == 'system.stats':
        return any(f'{data[k]:.1f}' in answer or str(round(data[k])) in answer
                   for k in ('cpu_percent', 'ram_percent'))
    if name.startswith('process.top_'):
        return any(r.get('name', '').casefold() in answer.casefold() for r in data.get('processes', [])[:3])
    if name == 'time.now':
        return bool(re.search(r'\b\d{1,2}:\d{2}|\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', answer))
    if name == 'system.info':
        return bool(re.search(r'\b(?:Windows|Linux|processor|core|RAM|memory|GB)\b', answer, re.I))
    if name.startswith('disk.'):
        return bool(re.search(r'\d+(?:\.\d+)?\s*(?:GB|GiB|MB|TB|bytes)', answer, re.I))
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path('src'))
    parser.add_argument('--cases', type=Path, default=Path('evals/phase1/development.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--repeats', type=int, default=1)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()))
    from hanni.config.loader import load_config
    from hanni.tools.registry import build_default_registry
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    from hanni.core.orchestrator import TextSession, system_prompt_for
    from hanni.models.client import LlamaCppClient
    from hanni.evals.isolation import isolated_host
    import hanni.reliability.verification as verification
    import psutil
    import httpx
    freeze_root = Path('evals/phase1')
    freeze = json.loads((freeze_root / 'freeze.json').read_text())
    for name, digest in freeze.items():
        if hashlib.sha256((freeze_root / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Frozen heldout/scoring changed; evaluation refused.')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    output = {'scope': 'LIVE_LOCAL_MODEL_AND_READ_TOOLS' if args.live else 'METADATA_ONLY_NO_EXECUTION',
              'source_root': str(args.source_root), 'cases_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
              'freeze': freeze, 'records': [], 'routing': [],
              'owner_speech_to_audible': {'status': 'NOT TESTED', 'reason': 'No physical owner-speech/acoustic-onset test.'},
              'server_queue_ms': {'status': 'NOT MEASURED', 'reason': 'No independently observable server admission timestamp.'}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    safe = {'system.stats', 'system.info', 'process.top_cpu', 'process.top_memory',
            'disk.usage', 'disk.free_space', 'time.now'}
    with tempfile.TemporaryDirectory(prefix='hanni-phase1-', ignore_cleanup_errors=True) as temp:
        config = load_config(Path('config'), data_dir=Path(temp), env={})
        registry = build_default_registry(config)
        host = McpHost(registry, read_only=config.hanni.mcp.read_only,
                       max_tools=config.hanni.mcp.max_tools_per_turn,
                       allowed_actions=config.hanni.mcp.allowed_actions)
        metadata = isolated_host(host)
        defined = {d.name for d in registry.definitions()}
        for case in cases:
            started = time.perf_counter()
            routed = metadata.route(case['query'], history=case.get('history', ()))
            retrieved = [t.capability_id for t in routed.tools]
            groups = case['required_groups']
            supported = all(any(n in defined for n in group) for group in groups)
            passed = all(set(group) & set(retrieved) for group in groups) if groups else not retrieved
            output['routing'].append({'id': case['id'], 'selected': retrieved, 'status': routed.status,
                                      'ms': (time.perf_counter() - started) * 1000,
                                      'supported': supported, 'tool_case': bool(groups), 'pass': bool(passed)})
        if args.live:
            spec = config.models.supervisor
            with httpx.Client(timeout=5, trust_env=False) as http:
                ids = http.get(spec.endpoint.rstrip('/').removesuffix('/v1') + '/v1/models').json()
                if spec.api_model not in [r.get('id') for r in ids.get('data', [])]:
                    raise RuntimeError('The live loopback model is not the configured default. No benchmark ran.')
                props = http.get(spec.endpoint.rstrip('/').removesuffix('/v1') + '/props').json()
            output['hardware'] = {'os': platform.platform(), 'cpu': platform.processor(),
                                  'logical_cpus': psutil.cpu_count(), 'ram_bytes': psutil.virtual_memory().total,
                                  'model_file': spec.model_file, 'api_model': spec.api_model,
                                  'configured_context': spec.context_length, 'configured_parallel': spec.parallel,
                                  'configured_temperature': spec.temperature, 'configured_top_p': spec.top_p,
                                  'configured_max_tokens': spec.max_tokens, 'thinking': spec.thinking_enabled,
                                  'observed_model_path': props.get('model_path'),
                                  'observed_settings': props.get('default_generation_settings'),
                                  'slots': props.get('total_slots')}
            from hanni.models.resource_manager import snapshot_resources
            output['hardware']['observed_local_resources'] = snapshot_resources(cpu_interval=0).to_dict()
            client = LlamaCppClient(spec, max_attempts=1)
            for repeat in range(args.repeats):
                for case in cases:
                    if case['required_groups'] and not case.get('live'):
                        continue
                    record = {'id': case['id'], 'repeat': repeat, 'routing_ms': 0., 'tool_ms': 0.,
                              'verification_ms': 0., 'model_calls_ms': [], 'model_first_token_ms': None,
                              'server_queue_ms': None, 'local_lease_wait_ms': None,
                              'first_visible_chunk_ms': None, 'first_useful_visible_ms': None, 'executed': []}
                    base = TextSession(client, system_prompt=system_prompt_for(config.hanni.personality))
                    for prior in case.get('history', []):
                        if prior.get('role') == 'user':
                            base.record_turn(prior['content'], 'A previous resource check was requested.')
                    session = McpToolSession(base, client, host, max_rounds=config.hanni.mcp.max_tool_rounds)
                    started = time.perf_counter()
                    real_route, real_call = host.route, host.call
                    real_complete, real_stream = client.complete_with_tools, client.stream_chat
                    def route(*a, **k):
                        at = time.perf_counter()
                        try: return real_route(*a, **k)
                        finally: record['routing_ms'] += (time.perf_counter() - at) * 1000
                    def call(tool, arguments, **k):
                        if tool.capability_id not in safe:
                            return {'name': tool.capability_id, 'ok': False, 'message': 'Evaluation forbids this handler.',
                                    'data': {}, 'error': {'code': 'EVALUATION_DENIED', 'retryable': False}}
                        at = time.perf_counter()
                        result = real_call(tool, arguments, **k)
                        record['tool_ms'] += (time.perf_counter() - at) * 1000
                        record['executed'].append({'name': tool.capability_id, 'ok': result.get('ok'),
                                                   'data': result.get('data'), 'verification': result.get('verification')})
                        return result
                    def complete(*a, **k):
                        at = time.perf_counter()
                        try: return real_complete(*a, **k)
                        finally: record['model_calls_ms'].append((time.perf_counter() - at) * 1000)
                    def stream(*a, **k):
                        at = time.perf_counter()
                        first = True
                        try:
                            for part in real_stream(*a, **k):
                                if first and part.strip():
                                    record['model_first_token_ms'] = (time.perf_counter() - at) * 1000
                                    first = False
                                yield part
                        finally: record['model_calls_ms'].append((time.perf_counter() - at) * 1000)
                    def timed_verify(fn):
                        def wrapped(*a, **k):
                            at = time.perf_counter()
                            try: return fn(*a, **k)
                            finally: record['verification_ms'] += (time.perf_counter() - at) * 1000
                        return wrapped
                    answer = ''
                    with ExitStack() as stack:
                        for obj, attr, replacement in ((host, 'route', route), (host, 'call', call),
                                                       (client, 'complete_with_tools', complete), (client, 'stream_chat', stream)):
                            stack.enter_context(patch.object(obj, attr, replacement))
                        for attr in ('inspect_result', 'verify_action'):
                            stack.enter_context(patch.object(verification, attr, timed_verify(getattr(verification, attr))))
                        try:
                            for part in session.stream_response(case['query']):
                                if record['first_visible_chunk_ms'] is None and part.strip():
                                    record['first_visible_chunk_ms'] = (time.perf_counter() - started) * 1000
                                answer += part
                                if record['first_useful_visible_ms'] is None and re.search(r'[.!?](?:\s|$)', answer):
                                    record['first_useful_visible_ms'] = (time.perf_counter() - started) * 1000
                        except Exception as exc:
                            record['error'] = type(exc).__name__
                    record['total_ms'] = (time.perf_counter() - started) * 1000
                    record['answer'] = answer
                    record['core_timings'] = getattr(session, 'last_metrics', None)
                    record['rediscovered'] = list(getattr(session, 'last_discovery', ()))
                    record['chars'] = len(answer)
                    record['words'] = len(answer.split())
                    record['sentences'] = len(sentences(answer))
                    record['brief'] = bool(answer) and record['sentences'] <= 3 and all(len(s.split()) <= 35 for s in sentences(answer))
                    if record['first_useful_visible_ms'] is None and answer.strip():
                        record['first_useful_visible_ms'] = record['total_ms']
                    groups = case['required_groups']
                    record['simple_success'] = (bool(answer) and not record.get('error') and all(any(
                        e['name'] in group and e['ok'] and independently_valid(e['name'], e['data'])
                        and evidence_in_answer(e['name'], e['data'], answer) for e in record['executed']) for group in groups)) if groups else None
                    output['records'].append(record)
                    args.output.write_text(json.dumps(output, indent=2, default=str), encoding='utf-8')
                    print(case['id'], round(record['total_ms']), 'ms', record['words'], 'words', flush=True)
        tool_cases = [r for r in output['routing'] if r['tool_case'] and r['supported']]
        output['required_tool_recall'] = sum(r['pass'] for r in tool_cases) / max(1, len(tool_cases))
        output['required_tool_recall_counts'] = {'passed': sum(r['pass'] for r in tool_cases), 'total': len(tool_cases)}
        output['unsupported_case_ids'] = [r['id'] for r in output['routing'] if not r['supported']]
        output['latency'] = {field: percentiles([r[field] for r in output['records']]) for field in (
            'routing_ms', 'tool_ms', 'verification_ms', 'model_first_token_ms',
            'first_visible_chunk_ms', 'first_useful_visible_ms', 'total_ms')}
        output['brevity'] = sum(r['brief'] for r in output['records']) / max(1, len(output['records']))
        simple = [r for r in output['records'] if r['simple_success'] is not None]
        output['simple_task_success'] = sum(r['simple_success'] for r in simple) / len(simple) if simple else None
        from hanni.reliability.execution import close_service
        close_service(config.paths.data_dir)
    args.output.write_text(json.dumps(output, indent=2, default=str), encoding='utf-8')
    print('Recall:', output['required_tool_recall'], 'Simple:', output['simple_task_success'],
          'Brief:', output['brevity'], flush=True)


if __name__ == '__main__':
    main()

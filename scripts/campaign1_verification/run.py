"""Serial actual original-controller evaluation, private raw evidence and safe seams.

No model/service launch, foreign action, account access, voice or autonomy
startup. The caller must obtain the manager's quiet-interval coordination.
Final execution additionally requires a matching immutable production freeze.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from uuid import uuid4
import urllib.parse
import psutil
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
os.environ['HANNI_LAYA_SHADOW_ENABLED'] = '0'
from hanni.config.loader import load_config
from hanni.models.client import LlamaCppClient
from hanni.models.manager import ModelManager, install as install_manager
from hanni.core.orchestrator import TextSession, system_prompt_for
from hanni.tools.registry import build_default_registry
from hanni.cli import _wrap_mcp_session, _wrap_memory_session, _close_interactive_session
from scripts.campaign1_verification.recording import Recording, hooks, record_into
from scripts.campaign1_verification.fixtures import setup, substitute, install_seams
from scripts.campaign1_verification.contract import validate_case, menu_metrics

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf8')
    temporary.replace(path)

def sources():
    paths = [*(ROOT / 'src').rglob('*.py'), *(ROOT / 'config').rglob('*.yaml'), *(ROOT / 'config').rglob('*.yml'), *(ROOT / 'scripts/campaign1_verification').glob('*.py'), *(ROOT / 'scripts/campaign1_verification').glob('*.json'), *(ROOT / 'scripts/campaign1').glob('*.py'), *(ROOT / 'evals/campaign1').glob('fixture-sources*.json'), ROOT / 'docs/campaign1/SEMANTIC_RUBRIC.md', ROOT / 'scripts/v36_engineering/migrate_coverage.py', ROOT / 'evals/llm_tools/capability_coverage_v2.jsonl', ROOT / 'evals/llm_tools/capability_coverage_v2_migration.json']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))}

def identity(spec):
    port = urllib.parse.urlsplit(spec.endpoint).port
    listeners = {r.pid for r in psutil.net_connections(kind='tcp') if r.status == psutil.CONN_LISTEN and r.laddr.port == port}
    assert listeners == {38832}, 'Reviewed external model listener changed.'
    process = psutil.Process(38832)
    parent = process.parent()
    assert process.create_time() == 1791595415.4806464
    assert parent.pid == 46084 and parent.create_time() == 1791595411.2839503
    assert 'hanni.dashboard.launcher' in parent.cmdline()
    command = process.cmdline()
    flags = {'--alias': spec.api_model, '--parallel': '1', '-c': str(spec.context_length), '--device': 'Vulkan1', '--reasoning': 'off'}
    assert all((command.count(k) == 1 and command[command.index(k) + 1] == v for k, v in flags.items()))
    return {'pid': process.pid, 'create_time': process.create_time(), 'parent_pid': parent.pid, 'parent_create_time': parent.create_time(), 'command_sha256': hashlib.sha256(json.dumps(command).encode()).hexdigest(), 'rss_mb': process.memory_info().rss / 2 ** 20, 'host_ram_percent': psutil.virtual_memory().percent}

def deny_launch(*args, **kwargs):
    raise RuntimeError('Evaluation cannot launch a model or change an external service.')

def run_case(case, output, source_file, live):
    state = output / 'state'
    root = output / 'files'
    output.mkdir(parents=True, exist_ok=False)
    cfg = load_config(ROOT / 'config', data_dir=state, env={})
    production_spec = cfg.models.supervisor
    eval_spec = replace(production_spec, temperature=0.0, top_p=1.0, max_tokens=256)
    models = replace(cfg.models, models=tuple((eval_spec if m.id == eval_spec.id else m for m in cfg.models.models)))
    cfg = replace(cfg, models=models, hanni=replace(cfg.hanni, model_routing=replace(cfg.hanni.model_routing, max_fallbacks=0), mcp=replace(cfg.hanni.mcp, max_tool_rounds=3)))
    setup_receipt = setup(case, root, state, source_file)
    registry = build_default_registry(cfg, data_dir=state)
    known = {d.name for d in registry.definitions()}
    validate_case(case, known)
    events = (output / 'events.jsonl').open('x', encoding='utf8')
    active_dispatch = [None]
    turn_dispatches = []

    def emit(data):
        if data.get('kind') == 'validated_handler_arguments':
            turn_dispatches.append(dict(data))
        if data.get('kind') == 'validated_handler_arguments' and active_dispatch[0] is not None and (data['tool'] == active_dispatch[0]['tool']):
            from copy import deepcopy
            active_dispatch[0]['effective_arguments'] = deepcopy(data['arguments'])
            active_dispatch[0]['effective_arguments_scope'] = 'post original authorization/validation handler input'
        events.write(json.dumps(data, ensure_ascii=False, default=str) + '\n')
        events.flush()
    session = None
    manager = None
    before = None
    closed = {}
    records = []
    try:
        emit({'kind': 'fixture_setup', 'receipt': setup_receipt})
        install_seams(registry, case, root, state, source_file, emit)
        if live:
            before = identity(eval_spec)
            manager = ModelManager(cfg, launch=deny_launch, startup_timeout=5)
            install_manager(manager)
            assert LlamaCppClient(eval_spec).health().ok, 'Original model is unavailable.'
        base = TextSession(LlamaCppClient(eval_spec), system_prompt=system_prompt_for(cfg.hanni.personality))
        session = _wrap_mcp_session(cfg, base, client=base.client, registry=registry)
        mcp_session = session
        host = session.host
        profile = case['fixture'].get('profile', case['fixture'].get('routing_profile', 'owner'))
        if profile in {'owner_reviewed_isolated_actions', 'explicit_controlled_actions'}:
            actions = case['fixture'].get('allowed_isolated_actions', case['fixture'].get('allowed_actions', []))
            host.allowed_actions = tuple(dict.fromkeys((*cfg.hanni.mcp.allowed_actions, *actions)))
        install_seams(registry, case, root, state, source_file, emit)
        original_route = host.route
        original_call = host.call
        fixed_now = datetime.fromisoformat(case['fixture'].get('fixed_clock', case['fixture'].get('now', '2026-10-12T10:15:00-04:00')))
        turn_routes = []
        turn_tools = []
        frozen_decisions = []
        route_depth = [0]
        route_order = [0]
        capture_native_routes = [True]

        def route(query, **options):
            options.setdefault('now', fixed_now)
            depth = route_depth[0]
            entry_order = route_order[0]
            route_order[0] += 1
            route_depth[0] += 1
            try:
                decision = original_route(query, **options)
            finally:
                route_depth[0] -= 1
            if not capture_native_routes[0]:
                return decision
            if depth == 0:
                frozen_decisions.append(decision)
            row = {'query': query, 'status': decision.status, 'confidence': decision.confidence, 'route_depth': depth, 'route_entry_order': entry_order, 'families': decision.families, 'subintents': decision.subintents, 'required_groups': getattr(decision, 'required_groups', ()), 'blocked_capabilities': decision.blocked_capabilities, 'tools': [asdict(t) for t in decision.tools]}
            turn_routes.append(row)
            emit({'kind': 'original_menu', **row})
            return decision

        def call(tool, arguments, **options):
            row = {'tool': tool.capability_id, 'wire_name': tool.wire_name, 'model_arguments': dict(arguments), 'fixed_arguments': dict(tool.fixed_arguments), 'premerge_argument_estimate': {**arguments, **tool.fixed_arguments}, 'effective_arguments': None}
            turn_tools.append(row)
            emit({'kind': 'original_host_call_started', **row})
            previous = active_dispatch[0]
            active_dispatch[0] = row
            try:
                result = original_call(tool, arguments, **options)
                row['result'] = result
                emit({'kind': 'original_host_call_finished', **row})
                return result
            except BaseException as exc:
                row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
                emit({'kind': 'original_host_call_failed', **row})
                raise
            finally:
                active_dispatch[0] = previous
        host.route = route
        host.call = call
        session = _wrap_memory_session(cfg, session, source='campaign1-isolated-evaluation', registry=registry, emergency_stop=registry.context.emergency_stop)
        for message in case.get('history', []):
            if isinstance(message, dict) and message.get('role') in {'user', 'assistant'}:
                base._history.append(substitute(message, root))
                base._history_times.append(base._clock())
        if live:
            assert host_client(session).health().ok, 'Original adaptive local probe is unavailable.'
        save(output / 'configuration.json', {'case_id': case['id'], 'production_model': asdict(production_spec), 'evaluation_model': asdict(eval_spec), 'routing_max_fallbacks': 0, 'profile': profile, 'read_only': host.read_only, 'allowed_actions': host.allowed_actions, 'registered_base_count': len(known), 'runtime_count': len(registry.definitions()), 'fixed_routing_clock': fixed_now.isoformat(), 'original_pure_tool_clocks': 'timekeep handler module clock controlled to declared fixture instant; process-global clocks real', 'external_model_before': before, 'live': live})
        save(output / 'registry-contracts.json', {'tools': [{'name': d.name, 'wire_name': host._wire_name(d.name), 'aliases': d.aliases, 'argument_schema': d.argument_schema(), 'permission_level': d.permission_level, 'risk_level': d.risk_level, 'side_effect': d.side_effect, 'host_allowed': host._allowed(d)} for d in registry.definitions()], 'profiles': {k: asdict(v) for k, v in cfg.permissions.profiles.items()}, 'read_only': host.read_only, 'allowed_actions': host.allowed_actions})
        turns = case.get('turns') or [case['query']]
        oracles = case['expected'].get('turns') or [case['expected']]
        for index, (query, oracle) in enumerate(zip(turns, oracles)):
            if (output.parent.parent / 'STOP').exists():
                break
            actual_query = substitute(query, root)
            turn_routes.clear()
            turn_tools.clear()
            frozen_decisions.clear()
            turn_dispatches.clear()
            route_order[0] = 0
            pre_history = base.history
            pre_messages = mcp_session._messages(actual_query, '')
            recorder = Recording(emit)
            began = time.perf_counter()
            response = []
            error = None
            probe = None
            probe_recorder = Recording(emit)
            probe_elapsed = None
            if live:
                with record_into(recorder):
                    try:
                        for text in session.stream_response(actual_query, max_tokens=256, temperature=0.0, top_p=1.0):
                            response.append(text)
                            emit({'kind': 'controller_text_chunk', 'turn': index, 'text': text})
                    except BaseException as exc:
                        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
                controller_elapsed = (time.perf_counter() - began) * 1000
                if not recorder.calls:
                    if frozen_decisions:
                        decision = frozen_decisions[0]
                    else:
                        capture_native_routes[0] = False
                        try:
                            decision = original_route(actual_query, history=pre_history, now=fixed_now)
                        finally:
                            capture_native_routes[0] = True
                    probe_began = time.perf_counter()
                    probe = {'scope': 'separate diagnostic selection; no dispatch or controller answer substitution', 'menu': [asdict(t) for t in decision.tools], 'menu_provenance': 'first_original_controller_menu' if frozen_decisions else 'separate_diagnostic_derived_menu_from_original_router', 'original_controller_menu_was_available': bool(frozen_decisions)}
                    with record_into(probe_recorder):
                        try:
                            with __import__('hanni.models.adaptive', fromlist=['model_request_scope']).model_request_scope(task_category='tool_selection', local_only=True, allow_legacy_default=True):
                                answer = host_client(session).complete_with_tools(pre_messages, tools=[t.openai_schema() for t in decision.tools], max_tokens=256, temperature=0.0, top_p=1.0)
                            probe.update(content=answer.content, tool_calls=[asdict(t) for t in answer.tool_calls])
                        except BaseException as exc:
                            probe['error'] = {'type': type(exc).__name__, 'message': str(exc)}
                    probe_elapsed = (time.perf_counter() - probe_began) * 1000
            else:
                route(actual_query, history=pre_history)
                controller_elapsed = (time.perf_counter() - began) * 1000
            row = {'case_id': case['id'], 'turn': index, 'query': actual_query, 'family': case['family'], 'difficulty': case['difficulty'], 'controller_response': ''.join(response), 'controller_error': error, 'original_routes': list(turn_routes), 'primary_original_menu': next((r for r in turn_routes if r.get('route_depth') == 0), None), 'tool_calls': list(turn_tools), 'model_calls': recorder.calls, 'native_menu_available': bool(frozen_decisions), 'authorized_handler_dispatches': list(turn_dispatches), 'diagnostic_probe': probe, 'diagnostic_model_calls': probe_recorder.calls, 'controller_elapsed_ms': controller_elapsed, 'diagnostic_elapsed_ms': probe_elapsed, 'elapsed_ms': (time.perf_counter() - began) * 1000, 'menu_metrics': menu_metrics([t.capability_id for t in frozen_decisions[0].tools] if frozen_decisions else [], oracle), 'effect_scope': 'foreign/provider controlled; original authorization; owned originals explicitly recorded', 'live': live}
            records.append(row)
            save(output / f'turn-{index:02}.json', row)
        save(output / 'completed.json', {'case_id': case['id'], 'turns': len(records), 'planned_turns': len(turns), 'model_calls': sum((len(r['model_calls']) for r in records)), 'diagnostic_model_calls': sum((len(r['diagnostic_model_calls']) for r in records)), 'live': live})
        return records
    finally:
        try:
            _close_interactive_session(session, registry=registry)
        except Exception as exc:
            closed['session_cleanup_error'] = str(exc)
        if manager:
            closed['manager_owned_processes'] = [getattr(e.process, 'pid', None) for e in manager.entries.values() if e.process is not None]
            assert not closed['manager_owned_processes']
            manager.close()
            install_manager(None)
        if before:
            after = identity(eval_spec)
            closed['external_after'] = after
            closed['external_original_preserved'] = all((after[k] == before[k] for k in ('pid', 'create_time', 'parent_pid', 'parent_create_time', 'command_sha256')))
        closed['closed'] = True
        save(output / 'closed.json', closed)
        events.close()

def host_client(session):
    while session is not None:
        if hasattr(session, 'host'):
            return session.client
        session = getattr(session, 'fallback_session', None)
    raise RuntimeError('Original MCP model client was unavailable.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fixture-sources', type=Path, default=ROOT / 'evals/campaign1/fixture-sources.json')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--freeze-proof', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/campaign1-verifier').resolve()) and (not output.exists())
    raw = args.corpus.read_text(encoding='utf8')
    corpus = json.loads(raw) if args.corpus.suffix == '.json' else None
    cases = corpus['cases'] if corpus else [json.loads(x) for x in raw.splitlines() if x.strip()]
    final = any((c['scope'] == 'isolated final' for c in cases))
    if final:
        assert corpus and sha(args.corpus) == 'b96221d8fe027ede7cfb1c75c059e50fa664b918cc4a4f092f08855a21174610'
        assert args.live and args.freeze_proof and (not args.ids) and (not args.limit), 'Final requires whole frozen campaign, no subset or preview.'
        proof = json.loads(args.freeze_proof.read_text(encoding='utf8'))
        assert proof['source_hashes'] == sources()
        assert args.fixture_sources.resolve() == (ROOT / 'evals/campaign1/fixture-sources-v2.json').resolve()
        assert sha(args.fixture_sources) == '29bc6a44986dd5b46dc8432d2eb7199e0588970f42f7f47d1b767f3acab2c50a'
        claim = args.corpus.parent / 'execution-claimed.json'
        assert not claim.exists(), 'This sealed final has already been claimed; no final-case retry is allowed.'
    if args.ids:
        cases = [c for c in cases if c['id'] in args.ids]
    if args.limit:
        cases = cases[:args.limit]
    assert cases
    output.mkdir(parents=True)
    save(output / 'ownership.json', {'helper_pid': os.getpid(), 'helper_create_time': psutil.Process().create_time(), 'helper_command_sha256': hashlib.sha256(json.dumps(psutil.Process().cmdline()).encode()).hexdigest(), 'process_scope': 'owned serial evaluation CLI only; original model/dashboard external and preserved', 'full_hanni_started': False, 'remote_helpers_started': False, 'model_launch_allowed': False})
    if final:
        with claim.open('x', encoding='utf8') as stream:
            json.dump({'output': str(output), 'claimed_at': time.time(), 'corpus_sha256': sha(args.corpus), 'freeze_proof_sha256': sha(args.freeze_proof), 'no_case_retry': True}, stream, indent=2)
    fixture_sources = json.loads(args.fixture_sources.read_text(encoding='utf8'))
    save(output / 'protocol.json', {'nonce': uuid4().hex, 'corpus_sha256': sha(args.corpus), 'python_runtime': {'version': sys.version, 'executable': sys.executable, 'pycache_prefix': sys.pycache_prefix}, 'fixture_sources_sha256': sha(args.fixture_sources), 'source_hashes': sources(), 'case_count': len(cases), 'planned_owner_turns': sum((len(c.get('turns') or [c['query']]) for c in cases)), 'final': final, 'live': args.live, 'model_profile': {'temperature': 0, 'top_p': 1, 'max_tokens': 256, 'max_tool_rounds': 3}, 'no_case_retry': True, 'max_inflight': 1, 'diagnostic_only_when_controller_model_calls_zero': True, 'raw_http_error_body_limit': 'Original HTTP error bodies not consumed by observer; error type/code/message retained.'})
    began = time.perf_counter()
    results = []
    failures = []
    with hooks():
        for case in cases:
            if (output / 'STOP').exists():
                break
            if final and (sources() != proof['source_hashes'] or sha(args.corpus) != 'b96221d8fe027ede7cfb1c75c059e50fa664b918cc4a4f092f08855a21174610'):
                failures.append({'case_id': case['id'], 'error_type': 'FINAL_SOURCE_CHANGED', 'message': 'Source/config/harness/fixture changed; stopped before dispatch, remaining cases NOT TESTED.'})
                save(output / 'failures.json', failures)
                break
            try:
                results.extend(run_case(case, output / 'cases' / case['id'], fixture_sources, args.live))
            except Exception as exc:
                failures.append({'case_id': case['id'], 'error_type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()})
                save(output / 'failures.json', failures)
            save(output / 'progress.json', {'completed_owner_turns': len(results), 'planned_cases': len(cases), 'case_failures': len(failures), 'model_calls': sum((len(r['model_calls']) for r in results)), 'diagnostic_model_calls': sum((len(r['diagnostic_model_calls']) for r in results)), 'elapsed_seconds': time.perf_counter() - began})
    summary = {'planned_cases': len(cases), 'completed_owner_turns': len(results), 'case_failures': len(failures), 'model_calls': sum((len(r['model_calls']) for r in results)), 'diagnostic_model_calls': sum((len(r['diagnostic_model_calls']) for r in results)), 'elapsed_seconds': time.perf_counter() - began, 'source_unchanged': sources() == json.loads((output / 'protocol.json').read_text(encoding='utf8'))['source_hashes']}
    save(output / 'summary.json', summary)
    print(json.dumps(summary))
if __name__ == '__main__':
    main()

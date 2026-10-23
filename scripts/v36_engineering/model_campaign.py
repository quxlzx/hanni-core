"""Resumable real-model turns through ORIGINAL configured conversation pipeline.

No fake model, tool-selection answer or success receipt exists in this harness.
Low-level Google/clipboard dependencies are controlled. Unsafe allowed actions
receive an explicit fixture availability rejection, not a fabricated execution.
Read-only ordinary tools execute their original handlers against live OS or
synthetic files. Existing MCP policy remains unchanged.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import GoogleProvider, GoogleVault
from hanni.cli import _wrap_mcp_session, _wrap_memory_session, _close_interactive_session
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession, system_prompt_for
from hanni.models import create_client
from hanni.tools import build_default_registry


class RecordingClient:
    def __init__(self, original):
        self.original = original
        self.records = []

    def complete_with_tools(self, messages, **kwargs):
        record = {'kind': 'tools', 'messages': messages, 'kwargs': kwargs}
        self.records.append(record)
        started = time.perf_counter()
        try:
            turn = self.original.complete_with_tools(messages, **kwargs)
            record['output'] = asdict(turn)
            return turn
        except Exception as error:
            record['error'] = {'class': type(error).__name__, 'message': str(error)}
            raise
        finally:
            # Snapshot the input now: controller appends later messages in-place.
            record['messages'] = json.loads(json.dumps(messages, default=str))
            record['latency_ms'] = (time.perf_counter()-started)*1000

    def stream_chat(self, messages, **kwargs):
        record = {'kind': 'stream_chat', 'messages': messages, 'kwargs': kwargs}
        self.records.append(record)
        started, parts = time.perf_counter(), []
        try:
            for chunk in self.original.stream_chat(messages, **kwargs):
                parts.append(chunk)
                yield chunk
            record['output'] = ''.join(parts)
        except Exception as error:
            record['partial_output'] = ''.join(parts)
            record['error'] = {'class': type(error).__name__, 'message': str(error)}
            raise
        finally:
            record['messages'] = json.loads(json.dumps(messages, default=str))
            record['latency_ms'] = (time.perf_counter()-started)*1000

    def chat(self, messages, **kwargs):
        return ''.join(self.stream_chat(messages, **kwargs))


def _boundary_error(name, reason):
    return {'name': name, 'ok': False, 'message': reason,
            'data': {'campaign_execution': 'blocked_before_handler'},
            'error': {'code': 'CAMPAIGN_ISOLATION_BOUNDARY', 'retryable': False}}


def bind_recording_boundary(host, fixture_root, records):
    original = host.call
    root = Path(fixture_root).resolve()
    unsafe = {'app.open', 'browser.open_url', 'folder.open', 'file.open',
              'media.play_pause', 'media.next_track', 'media.previous_track', 'media.stop',
              'spotify.launch', 'spotify.focus', 'spotify.play_pause', 'spotify.next',
              'spotify.previous', 'spotify.search', 'spotify.open_uri', 'clipboard.write',
              'timer.set', 'notify.toast'}
    path_family = {'file', 'archive', 'git', 'folder', 'project'}
    file_tree_caps = {'disk.folder_size', 'disk.largest_files', 'disk.largest_folders'}
    keys = ('path', 'root', 'source', 'destination', 'archive', 'left', 'right')

    def call(tool, arguments, *args, **kwargs):
        effective = {**arguments, **tool.fixed_arguments}
        record = {'capability_id': tool.capability_id, 'model_arguments': dict(arguments),
                  'effective_arguments': effective, 'handler_invoked': False}
        records.append(record)
        started = time.perf_counter()
        try:
            if tool.capability_id in unsafe:
                result = _boundary_error(tool.capability_id,
                    'This campaign does not perform live window, app, media, clipboard or notification changes. The selected action was not executed; original handler direct tests use controlled OS dependencies separately.')
            elif (tool.capability_id.split('.')[0] in path_family or tool.capability_id in file_tree_caps) and (
                    not any(effective.get(key) for key in keys) or any(
                        not Path(str(effective[key])).resolve().is_relative_to(root)
                        for key in keys if effective.get(key))):
                result = _boundary_error(tool.capability_id,
                    'The generated file arguments were not fully confined to the disposable campaign directory. No personal file was read or changed.')
            else:
                record['handler_invoked'] = True
                result = original(tool, arguments, *args, **kwargs)
            record['result'] = result
            return result
        finally:
            record['latency_ms'] = (time.perf_counter()-started)*1000
    host.call = call


def run(args):
    cohort_path = args.cases.resolve()
    cohort_bytes = cohort_path.read_bytes()
    digest = hashlib.sha256(cohort_bytes).hexdigest()
    if digest != cohort_path.with_suffix('.sha256').read_text().strip():
        raise ValueError('The sealed cohort hash changed.')
    cohort = json.loads(cohort_bytes)
    identity = json.loads(args.identity.read_text(encoding='utf-8'))
    config = load_config(Path(identity['config_dir']), data_dir=args.fixture_root/'state', env={})
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ['HANNI_LAYA_SHADOW_ENABLED'] = '0'
    os.environ['HANNI_V36_FIXTURE'] = 'cobalt-lighthouse'
    registry = build_default_registry(config)
    google = GoogleProvider()
    registry.google_access._vault = GoogleVault()
    registry.google_access.transport = google
    raw_client = create_client(config)
    if not raw_client.health().ok:
        raise RuntimeError('The sole configured model endpoint is unavailable. No runtime/download fallback.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.output.exists():
        for line in args.output.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            if record.get('cohort_sha256') != digest:
                raise ValueError('Existing results belong to another cohort.')
            done.add(record['case_id'])
    candidates = [case for case in cohort['cases'] if case['id'] not in done]
    if args.limit:
        candidates = candidates[:args.limit]
    completed, campaign_start = 0, time.monotonic()
    try:
        with args.output.open('a', encoding='utf-8') as output:
            for case in candidates:
                if time.monotonic()-campaign_start >= args.max_seconds:
                    break
                client = RecordingClient(raw_client)
                base = TextSession(client, system_prompt=system_prompt_for(config.hanni.personality))
                mcp = _wrap_mcp_session(config, base, client=client, registry=registry)
                host_records = []
                bind_recording_boundary(mcp.host, args.fixture_root, host_records)
                controller = _wrap_memory_session(config, mcp, source='v36-controlled-model',
                    registry=registry, emergency_stop=registry.context.emergency_stop)
                record = {'version': 1, 'case_id': case['id'], 'capability_id': case['capability_id'],
                          'cohort_sha256': digest, 'request': case['request'],
                          'accepted_operation_aliases': case['acceptable_equivalent_capabilities'],
                          'model': asdict(config.models.supervisor),
                          'environment': 'original controller, isolated files/state, controlled Google/clipboard dependencies, live read-only OS',
                          'verification_status': 'PENDING_INDEPENDENT_REVIEW',
                          'original_policy_eligible': mcp.host._allowed(registry.get(case['capability_id']))}
                start = time.perf_counter()
                try:
                    decision = mcp.host.route(case['request'])
                    record['routing'] = {'status': decision.status,
                        'menu': [tool.capability_id for tool in decision.tools],
                        'blocked_capabilities': list(decision.blocked_capabilities)}
                    with patch('hanni.tools.content.run_powershell',
                               side_effect=lambda command, **kwargs: 'cobalt lighthouse' if command == 'Get-Clipboard -Raw' else (_ for _ in ()).throw(ValueError('Unexpected clipboard fixture command'))):
                        record['response'] = ''.join(controller.stream_response(case['request']))
                    record['controller_trace'] = mcp.last_trace
                    if not client.records:
                        # Some original calendar/email/action-denial fast paths do
                        # no inference. Preserve that real response and separately
                        # ask the same configured model about the sealed request,
                        # with no authority/tools. Never call this tool-selection.
                        record['response_only_diagnostic'] = ''.join(base.stream_response(case['request']))
                        record['model_evaluation_scope'] = 'Original controller deterministic path; additional genuine response-only inference with no tool menu/execution authority.'
                    else:
                        record['model_evaluation_scope'] = 'Original configured MCP/memory controller processed the request with actual model inference.'
                    calls = [call['name'] for inference in client.records
                             if isinstance(inference.get('output'), dict)
                             for call in inference['output'].get('tool_calls', [])]
                    exact = mcp.host._wire_name(case['capability_id'])
                    accepted = {mcp.host._wire_name(name) for name in case['acceptable_equivalent_capabilities']}
                    record['observed_model_wire_calls'] = calls
                    record['exact_capability_selected'] = exact in calls
                    record['operation_equivalent_selected'] = any(call in accepted for call in calls)
                    record['inference_requests'] = len(client.records)
                    record['selection_measurement'] = ('MEASURED' if any(row['kind']=='tools' for row in client.records)
                                                       else 'BLOCKED_OR_DETERMINISTIC_PATH_NO_MODEL_TOOL_MENU')
                    record['outcome'] = ('BLOCKED' if not record['original_policy_eligible'] else
                        'FAIL' if record['selection_measurement']=='MEASURED' and not record['operation_equivalent_selected'] else
                        'BLOCKED' if any(row['result'].get('error',{}).get('code')=='CAMPAIGN_ISOLATION_BOUNDARY' for row in host_records) else
                        'FAIL' if any(not row['result'].get('ok') for row in host_records) else
                        'MOCK_PASS' if any(row['capability_id'].startswith(('google', 'gmail', 'email', 'clipboard')) for row in host_records) else
                        'ISOLATED_PASS' if host_records and any(row['capability_id'].split('.')[0] in {'file','archive','git','note','todo'} for row in host_records) else
                        'LIVE_PASS' if host_records else 'BLOCKED')
                except Exception as error:
                    record['outcome'] = 'FAIL'
                    record['error'] = {'class': type(error).__name__, 'message': str(error)}
                finally:
                    record['latency_ms'] = (time.perf_counter()-start)*1000
                    record['actual_model_inferences'] = client.records
                    record['actual_tool_receipts'] = host_records
                    # Raw input/outputs remain ignored/private, never committed.
                    output.write(json.dumps(record, ensure_ascii=True, default=str)+'\n')
                    output.flush()
                    _close_interactive_session(controller)
                completed += 1
                print(json.dumps({'completed': completed, 'total_completed': len(done)+completed,
                                  'capability_id': case['capability_id'], 'outcome': record['outcome'],
                                  'latency_seconds': round(record['latency_ms']/1000,2)}), flush=True)
    finally:
        registry.context.reliability.close()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--fixture-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--max-seconds', type=int, default=7200)
    raise SystemExit(run(parser.parse_args()))

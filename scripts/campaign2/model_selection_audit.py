"""Actual guarded model-selection attempts, separately from retrieval and tool execution."""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
import psutil
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession, system_prompt_for
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.models.adaptive import AdaptiveModelEngine, model_request_scope
from hanni.models.client import LlamaCppClient
from hanni.reliability.execution import close_service
from hanni.tools.registry import build_default_registry
from scripts.campaign1_verification.recording import Recording, hooks, record_into
from scripts.campaign2.capability_audit import save
from scripts.campaign2.mcp_harness import OwnedHub

def selection(client, host, query, expected, model):
    decision = host.route(query)
    menu = list(decision.tools)
    recording = Recording(lambda event: None)
    receipt = {'query': query, 'menu': [asdict(t) for t in menu], 'expected': expected, 'scope': 'Separate actual guarded selection diagnostic; no tool is executed by this diagnostic.', 'resource_before': {'available_ram_bytes': psutil.virtual_memory().available, 'ram_percent': psutil.virtual_memory().percent}}
    eligible = any((host._allowed(host.registry.get(identity)) for identity in expected))
    receipt['target_host_eligible'] = eligible
    receipt['selection_oracle'] = 'one or more equivalent eligible choices, with no extra choices' if eligible else 'abstain from host-denied action'
    started = time.perf_counter()
    with record_into(recording):
        try:
            with model_request_scope(task_category='tool_selection', local_only=True, allow_legacy_default=True):
                turn = client.complete_with_tools([{'role': 'system', 'content': system_prompt_for(model.config.hanni.personality)}, {'role': 'user', 'content': query}], tools=[t.openai_schema() for t in menu])
            receipt['parsed_turn'] = asdict(turn)
            names = {t.wire_name: t.capability_id for t in menu}
            selected = [names.get(call.name, call.name) for call in turn.tool_calls]
            schema_errors = []
            for call in turn.tool_calls:
                tool = next((t for t in menu if t.wire_name == call.name), None)
                try:
                    if tool is None:
                        raise ValueError('Tool is not in presented menu')
                    host.registry.get(tool.capability_id).validate_arguments({**call.arguments, **tool.fixed_arguments})
                except Exception as exc:
                    schema_errors.append(str(exc))
            appropriate = bool(selected) and set(selected).issubset(set(expected)) if eligible else not selected
            if expected and any((identity.startswith('mcp.') for identity in expected)):
                appropriate = appropriate and len(turn.tool_calls) == 1 and (turn.tool_calls[0].arguments == {'calibration': 'AX-17'})
            receipt.update(selected_ids=selected, schema_errors=schema_errors, status='pass' if appropriate and (not schema_errors) else 'fail')
        except Exception as exc:
            receipt.update(status='blocked', reason='Original model inference admission or dependency refused the request.', error={'type': type(exc).__name__, 'message': str(exc)})
            if type(exc).__name__ == 'ModelSelectionError':
                with model_request_scope(task_category='tool_selection', local_only=True, allow_legacy_default=True):
                    request = client._request({}, tools=[t.openai_schema() for t in menu])
                messages = [{'role': 'system', 'content': system_prompt_for(model.config.hanni.personality)}, {'role': 'user', 'content': query}]
                inspected = model.select(replace(request, context_tokens=max(request.context_tokens, len(json.dumps(messages, ensure_ascii=False).encode())) + request.schema_tokens, schema_tokens=0))
                receipt['separate_admission_inspection'] = {'excluded': inspected['excluded'], 'reason': inspected['reason'], 'scope': 'Original selector diagnostic after refusal, not native error attribution.'}
    receipt.update(latency_ms=(time.perf_counter() - started) * 1000, model_calls=recording.calls, actual_model_http_requests=sum((len(row['http_attempts']) for row in recording.calls)))
    if not receipt['actual_model_http_requests']:
        receipt['status'] = 'blocked'
        receipt.setdefault('reason', 'No actual inference request was admitted; deterministic retrieval is separate.')
    return receipt

def run(scorecard, output, unknown_only=False):
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix='hanni-campaign2-model-') as folder, hooks():
        root = Path(folder)
        cfg = load_config(ROOT / 'config', data_dir=root / 'state', env={})
        registry = build_default_registry(cfg)
        engine = AdaptiveModelEngine(cfg)
        client = engine.wrap_client(LlamaCppClient(cfg.models.supervisor, max_attempts=cfg.hanni.recovery.max_attempts))
        host = McpHost(registry, read_only=cfg.hanni.mcp.read_only, allowed_actions=cfg.hanni.mcp.allowed_actions, max_tools=cfg.hanni.mcp.max_tools_per_turn)
        health = client.health()
        save(output / 'MODEL_HEALTH.json', {'ok': health.ok, 'defaults': {'temperature': cfg.models.supervisor.temperature, 'top_p': cfg.models.supervisor.top_p, 'max_tokens': cfg.models.supervisor.max_tokens}, 'scope': 'Existing model read-only probe; no launcher, ownership adoption, retraining or guard change.'})
        try:
            if not unknown_only:
                for case in json.loads(scorecard.read_text(encoding='utf8'))['capabilities']:
                    if 'query' not in case:
                        continue
                    equivalent = case['dimensions']['natural_language_selection']['receipt']['accepted_equivalents']
                    row = selection(client, host, case['query'], equivalent, engine)
                    row['capability_id'] = case['id']
                    rows.append(row)
                    save(output / 'receipts' / f"{case['id']}.json", row)
                    print(case['id'] + ': ' + row['status'], flush=True)
            with OwnedHub(root / 'unknown-server') as hub:
                tool = hub.tool('quartz.inspect_flux_band')
                identity = tool['internal_id']
                query = 'On Quartz Bench, inspect the flux band for calibration AX-17 and report the returned band and intensity.'
                unknown_host = McpHost(hub.registry, read_only=cfg.hanni.mcp.read_only, max_tools=cfg.hanni.mcp.max_tools_per_turn, allowed_actions=cfg.hanni.mcp.allowed_actions)
                row = selection(client, unknown_host, query, [identity], engine)
                row.update(capability_id=identity, original_name='quartz.inspect_flux_band', schema=tool['input_schema'], discovered_by_actual_sdk=True, model_retraining_performed=False)
                result = hub.call('quartz.inspect_flux_band', {'calibration': 'AX-17'})
                row['separate_original_registry_call'] = {'scope': 'Declared fixture arguments, not model inference completion', 'result': result.to_dict(), 'calls': hub.calls()}
                if row['status'] == 'pass':
                    base = TextSession(client, system_prompt=system_prompt_for(cfg.hanni.personality))
                    session = McpToolSession(base, client, unknown_host, max_rounds=cfg.hanni.mcp.max_tool_rounds, tool_result_chars=cfg.hanni.mcp.tool_result_chars)
                    recording = Recording(lambda event: None)
                    with record_into(recording):
                        try:
                            row['controller_answer'] = ''.join(session.stream_response(query))
                        except Exception as exc:
                            row['controller_error'] = str(exc)
                    row['controller_model_calls'] = recording.calls
                rows.append(row)
                save(output / 'UNKNOWN_TOOL_DEMO.json', row)
                print('unknown MCP tool: ' + row['status'], flush=True)
        finally:
            engine.close()
            close_service(root / 'state')
    report = {'captured_at': datetime.now(timezone.utc).isoformat(), 'attempts': len(rows), 'counts': {status: sum((row['status'] == status for row in rows)) for status in ('pass', 'fail', 'blocked')}, 'actual_model_http_requests': sum((row['actual_model_http_requests'] for row in rows)), 'scope': 'Guarded actual selection diagnostics; retrieval scorecard is separate; foreign actions never dispatched.'}
    save(output / 'SUMMARY.json', report)
    print(json.dumps(report))
    return report
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--scorecard', type=Path, default=ROOT / 'docs/campaign2/SCORECARD.json')
    p.add_argument('--output', type=Path, default=ROOT / 'docs/campaign2/model-evidence')
    p.add_argument('--unknown-only', action='store_true')
    a = p.parse_args()
    run(a.scorecard, a.output, a.unknown_only)

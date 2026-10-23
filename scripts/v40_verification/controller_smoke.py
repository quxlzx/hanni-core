"""Real default/adaptive original MCP controller turns; read-only OS/synthetic file."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src')]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession
from hanni.mcp.host import McpHost
from hanni.mcp.session import McpToolSession
from hanni.models.adaptive import AdaptiveModelEngine
from hanni.models.client import LlamaCppClient
from hanni.tools.registry import build_default_registry
from hanni.tools.google_access import GoogleAccess


def main():
    output = ROOT / 'data/v40-verification/controller-20261009-a'
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'synthetic-sensor-report.txt'
    source.write_text('dispatch_code=amber-7304\nThis is synthetic verification content.\n', encoding='utf8')
    cases = [{'id': 'cpu-ram-live', 'prompt': 'Check current CPU and RAM usage percentages.',
              'expected_capability': 'system.stats', 'source': 'live local OS read-only'},
             {'id': 'file-read-synthetic', 'prompt': f'Read the file at {source} and tell me its dispatch_code value.',
              'expected_capability': 'file.read', 'expected_literal': 'amber-7304', 'source': 'synthetic file'}]
    encoded = json.dumps(cases, sort_keys=True).encode()
    (output / 'protocol.json').write_bytes(encoded)
    (output / 'protocol.sha256').write_text(hashlib.sha256(encoded).hexdigest())
    class EmptyVault:
        def get(self, account): return None
        def labels(self): return ('personal', 'school')
        def preferences(self): return {}
    class OfflineGoogle(GoogleAccess):
        def __init__(self, vault=None, transport=None, timezone_name=None):
            super().__init__(EmptyVault(), transport, timezone_name)
    rows = []
    for arm in ('fixed', 'adaptive'):
        config = load_config(ROOT / 'config', data_dir=output / arm / 'state', env={})
        compute = ComputeScheduler(ComputeRegistry(ROOT / 'data')) if arm == 'adaptive' else None
        engine = AdaptiveModelEngine(config, compute_scheduler=compute) if arm == 'adaptive' else None
        raw = LlamaCppClient(config.models.supervisor, max_attempts=1)
        if engine:
            engine.refresh()
            context = json.loads((ROOT / 'data/v40-verification/capability-probes-20261009-a/results.json').read_text())[-1]
            engine.record_capability_evidence('local:supervisor', identity=engine.endpoint_identity('local:supervisor'),
                capabilities=['text', 'structured_json', 'tool_calling'], context_tokens=16384,
                observed_prompt_tokens=context['observed_prompt_tokens'], retrieval_passed=True,
                evidence_sha256=hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest(),
                environment='actual unchanged owned default weights/fullfile SHA; local16K q8KV synthetic probe')
        client = engine.wrap_client(raw) if engine else raw
        with patch('hanni.tools.google_access.GoogleAccess', OfflineGoogle):
            registry = build_default_registry(config)
        try:
            for case in cases:
                session = McpToolSession(TextSession(client), client, McpHost(registry, read_only=True,
                    max_tools=config.hanni.mcp.max_tools_per_turn, allowed_actions=()))
                records = []
                call = session.host.call
                def observed(tool, arguments, *args, **kwargs):
                    result = call(tool, arguments, *args, **kwargs)
                    records.append({'capability_id': tool.capability_id, 'arguments': dict(arguments), 'result': result})
                    return result
                session.host.call = observed
                row = {'arm': arm, 'case_id': case['id'], 'scope': case['source'], 'passed': False}
                began = time.perf_counter()
                try:
                    answer = ''.join(session.stream_response(case['prompt']))
                    row.update(answer=answer, original_receipts=records, trace=session.last_trace)
                    matched = [r for r in records if r['capability_id'] == case['expected_capability'] and r['result'].get('ok')]
                    literal = case.get('expected_literal')
                    row['passed'] = bool(matched) and (literal is None or literal in answer)
                    row['correct_tool_selection'] = bool(matched)
                    row['verified_receipt'] = any(r['result'].get('verification', {}).get('status') == 'VERIFIED' for r in matched)
                except Exception as error:
                    row.update(error_class=type(error).__name__)
                row['latency_ms'] = (time.perf_counter()-began)*1000
                if engine: row['routing_decisions'] = engine.snapshot()['decisions']
                rows.append(row)
                (output / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
                print(json.dumps({k: row.get(k) for k in ('arm','case_id','passed','correct_tool_selection','verified_receipt','latency_ms','error_class')}), flush=True)
        finally:
            if registry.context.reliability: registry.context.reliability.close()
            if engine: engine.close()
            if compute: compute.close()


if __name__ == '__main__':
    main()

"""Actual loopback planner + original workflow executor in owner-authorized temp storage.

No provider credentials, remote inference, or service lifecycle operations. Writes
are restricted to managed reports. Persist observations before temporary cleanup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from uuid import uuid4


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, default=Path('src'))
    p.add_argument('--cases', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--contract', choices=('legacy', 'intent'), default='legacy')
    args = p.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()))
    from hanni.config.loader import load_config
    from hanni.models.client import LlamaCppClient
    from hanni.tools.registry import build_default_registry
    from hanni.mcp.host import McpHost
    from hanni.workflows.service import WorkflowService
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    freeze_path = args.cases.parent / 'freeze.json'
    if freeze_path.exists():
        for name, digest in json.loads(freeze_path.read_text()).items():
            assert hashlib.sha256((args.cases.parent/name).read_bytes()).hexdigest() == digest, 'Frozen inputs changed'
    output = {'scope': 'LIVE_LOCAL_MODEL_ORIGINAL_WORKFLOW', 'contract': args.contract,
              'cases_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(), 'records': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='hanni-phase2-', ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            source = root / 'Owner authorized folder' / 'quarterly notes.txt'
            source.parent.mkdir()
            source.write_text('Orion: 12 completed tasks. Vega: 7 completed tasks. Next review: Friday.', encoding='utf-8')
            if case.get('duplicate_source'):
                other = source.parent/'second location'; other.mkdir()
                (other/source.name).write_text('Ambiguous second file.', encoding='utf-8')
            config = load_config(Path('config'), data_dir=root/'data', env={})
            registry = build_default_registry(config)
            # Explicit absent-provider fixture: never inspect the owner's vault.
            class AbsentVault:
                def get(self, account): return None
                def labels(self): return []
                def preferences(self): return {}
            registry.google_access._vault = AbsentVault()
            host = McpHost(registry, read_only=True, allowed_actions=(),
                           max_tools=config.hanni.mcp.max_tools_per_turn)
            client = LlamaCppClient(config.models.supervisor, max_attempts=1)
            health = client.health()
            if not health.ok:
                raise RuntimeError(health.render_text())
            proposals = []
            original_chat = client.chat
            def tracked_chat(messages, **kwargs):
                began = time.perf_counter()
                response = original_chat(messages, **kwargs)
                proposals.append({'duration_ms': (time.perf_counter()-began)*1000, 'response': response})
                return response
            client.chat = tracked_chat
            options = {} if args.contract == 'legacy' else {'planning_contract': 'intent'}
            service = WorkflowService(root/'data', protected_roots=(Path.cwd(),), **options)
            service.attach(registry, client, host=host,
                           resource_probe=lambda: {'allowed': True, 'ram_percent': 20, 'gpu': None})
            service.start()
            goal = case['goal'].replace('{source}', str(source)).replace('{root}', str(source.parent))
            def op(name, data):
                return service.mutate({'id': str(uuid4()), 'operation': name, 'data': data})
            started = time.perf_counter()
            detail = None
            try:
                key = op('goal.submit', {'goal': goal, 'mode': case.get('mode', 'supervised')})['workflow_id']
                detail = service.wait(key, timeout=150)
                planning_ms = (time.perf_counter()-started)*1000
                if case.get('positive', True) and detail['status'] == 'awaiting_plan_approval':
                    op('approve_plan', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
                    detail = service.detail(key)
                    op('start', {'workflow_id': key, 'expected_revision': detail['revision'], 'plan_hash': detail['plan_hash']})
                    detail = service.wait(key, timeout=90)
                if (case.get('positive', True) and case.get('report')
                        and detail['status'] == 'awaiting_step_approval'):
                    # Explicit fixture owner review: managed, evidence-bound report only.
                    grant = next(a for a in detail['approvals'] if a['kind']=='action' and a['state']=='pending')
                    step = next(s for s in detail['steps'] if s['step_id']==grant['step_id'])
                    assert step['kind']=='artifact' and step['capability_id']=='file.write'
                    assert Path(step['resolved_arguments']['path']).resolve().is_relative_to(service.artifacts_root)
                    op('approve_step', {'workflow_id': key, 'expected_revision': detail['revision'],
                       **{k: grant[k] for k in ('step_id','approval_id','plan_hash','argument_hash','definition_hash')}})
                    detail = service.wait(key, timeout=90)
                # No automatic approval of consequential step actions.
                checks = {}
                receipts = {s.get('capability_id'): s for s in detail['steps']}
                for cap in case.get('required', []):
                    checks[cap] = cap in receipts and receipts[cap]['status'] == 'verified'
                for cap, expected in case.get('arguments', {}).items():
                    actual = receipts.get(cap, {}).get('resolved_arguments') or {}
                    checks[cap+'_arguments'] = all(actual.get(k)==v for k, v in expected.items())
                if case.get('analysis'):
                    checked = [s for s in detail['steps'] if s['kind']=='analysis']
                    checks['cited_analysis'] = bool(checked) and all(s['status']=='verified' for s in checked)
                if 'file.read' in case.get('required', []):
                    checks['exact_source_contents'] = receipts.get('file.read', {}).get('result', {}).get('data', {}).get('text') == source.read_text()
                if case.get('locate'):
                    finds = [s for s in detail['steps'] if s.get('capability_id') in {'file.locate','file.search'}]
                    checks['located_unique_authorized_file'] = bool(finds) and any(
                        s['status']=='verified' and len(s.get('result', {}).get('data', {}).get('matches', []))==1
                        and s['result']['data']['matches'][0]['path']==str(source) for s in finds)
                if case.get('report'):
                    artifacts = [s for s in detail['steps'] if s['kind'] == 'artifact']
                    checks['saved_report_contents'] = bool(artifacts) and all(
                        Path(s.get('resolved_arguments', {}).get('path', '')).is_file()
                        and Path(s['resolved_arguments']['path']).read_text(encoding='utf-8') == s['resolved_arguments'].get('text')
                        for s in artifacts)
                    checked_values = []
                    for s in artifacts:
                        target = Path(s.get('resolved_arguments', {}).get('path', ''))
                        if target.is_file():
                            try:
                                checked_values.extend(o['value'] for o in json.loads(target.read_text(encoding='utf-8'))['observations'])
                            except (ValueError, KeyError, TypeError):
                                pass
                    checks['report_contains_observed_source_text'] = source.read_text() in checked_values
                if case.get('positive', True):
                    checks['multi_step'] = len(detail['steps']) >= case.get('min_steps', 1)
                passed = case.get('positive', True) and detail['status'] == 'completed' and bool(checks) and all(checks.values())
                followup_detail = None
                if case.get('followup'):
                    next_goal = case['followup'].replace('{source}',str(source)).replace('{root}',str(source.parent))
                    next_key = op('goal.submit', {'goal': next_goal, 'mode': 'supervised'})['workflow_id']
                    followup_detail = service.wait(next_key, timeout=150)
                    followup_checks = (followup_detail['status']=='completed'
                        and all(any(s.get('capability_id')==cap and s['status']=='verified' for s in followup_detail['steps'])
                                for cap in case['followup_required']))
                    checks['followup'] = followup_checks
                    passed = passed and followup_checks
                negative_boundary = False
                if not case.get('positive', True) and case.get('boundary_error'):
                    negative_boundary = (not any(i['write'] for i in detail['invocations'])
                                         and case['boundary_error'].casefold() in (detail.get('error') or '').casefold())
                output['records'].append({'id': case['id'], 'goal': goal, 'positive': case.get('positive', True),
                    'planning_or_first_boundary_ms': planning_ms, 'total_ms': (time.perf_counter()-started)*1000,
                    'independent_checks': checks, 'positive_pass': bool(passed), 'detail': detail,
                    'model_calls': proposals, 'negative_boundary_reached': negative_boundary,
                    'followup_detail': followup_detail,
                    'false_completion': bool(case.get('positive', True) and detail['status']=='completed' and not all(
                        v for k,v in checks.items() if k!='followup'))})
            except Exception as exc:
                output['records'].append({'id': case['id'], 'exception': str(exc), 'detail': detail, 'positive_pass': False})
            finally:
                service.close()
            args.output.write_text(json.dumps(output, indent=2, default=str), encoding='utf-8')
            print(case['id'], output['records'][-1].get('detail', {}).get('status'), output['records'][-1]['positive_pass'], flush=True)


if __name__ == '__main__':
    main()

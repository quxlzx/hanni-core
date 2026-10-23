"""Public requirement: only known independent local reads may run in parallel.

Actual SDK transport, approved dynamic registrations, scheduler and original
host calls; no handler substitute or permission promotion.
"""
import json
import time
from hanni.mcp.manager import MCPManager
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture
from tests.integration.test_mcp_hub_controller_verifier import approve
from tests.integration.test_mcp_hub_verifier import connected, entries, local_config
from tests.integration.test_workflow_service_verifier import criterion, queue_plan, row, step

def test_owner_classified_external_reads_do_not_infer_safe_local_parallelism(tmp_path):
    config, control, ledger = local_config(tmp_path / 'sdk')
    control.write_text(json.dumps({'delay': 1.0}), encoding='utf-8')
    client = QueuedStructuredClient()
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        manager = MCPManager(tmp_path / 'mcp-state', registry=fixture.registry)
        try:
            server = connected(manager, config)
            echo = approve(manager, server, 'mock.echo')
            status = approve(manager, server, 'mock.get_status')
            queue_plan(client, [step('echo', 'Use mock.echo to echo the supplied message.', criteria=[criterion('present', '/data')]), step('status', 'Use mock.get_status to read the integration fixture status.', criteria=[criterion('present', '/data')]), step('save', 'Save a report only after both observed results are verified.', kind='artifact', dependencies=['echo', 'status'])], [row('echo', echo['internal_id'], message='Explicit isolated parallelism probe.'), row('status', status['internal_id']), row('save', 'file.write', path='$artifact/report.txt', text='Observed provider results.')])
            key = fixture.submit('Use mock.echo and mock.get_status separately; preserve only verified observations.')
            fixture.await_state(key, 'awaiting_plan_approval')
            fixture.control(key, 'approve_plan')
            fixture.control(key, 'start')
            deadline = time.monotonic() + 4
            while not [r for r in entries(ledger) if r['event'] == 'call'] and time.monotonic() < deadline:
                time.sleep(0.01)
            time.sleep(0.2)
            calls = [r for r in entries(ledger) if r['event'] == 'call']
            observed = fixture.detail(key)
            evidence = {'calls_while_first_original_rpc_is_inflight': calls, 'step_states': {s['step_id']: s['status'] for s in observed['steps']}, 'worker_kinds': [w['kind'] for w in fixture.service.workers.values()], 'external_definitions': [echo['internal_id'], status['internal_id']], 'declared_sdk_delay_seconds': 1.0, 'observation_wait_after_first_call_seconds': 0.2}
            from pathlib import Path
            (tmp_path / 'm3-imported-parallel-evidence-cycle-1.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            assert len(calls) == 1, evidence
        finally:
            time.sleep(1.1)
            manager.close()

def test_distinct_sdk_sessions_do_not_infer_safe_local_parallelism(tmp_path):
    first_config, first_control, first_ledger = local_config(tmp_path / 'sdk-first')
    second_config, second_control, second_ledger = local_config(tmp_path / 'sdk-second')
    first_config['name'], second_config['name'] = ('First isolated provider', 'Second isolated provider')
    for control in (first_control, second_control):
        control.write_text(json.dumps({'delay': 1.0}), encoding='utf-8')
    client = QueuedStructuredClient()
    with ServiceFixture(tmp_path / 'run', client=client) as fixture:
        manager = MCPManager(tmp_path / 'mcp-state', registry=fixture.registry)
        try:
            first_server = connected(manager, first_config)
            second_server = connected(manager, second_config)
            echo = approve(manager, first_server, 'mock.echo')
            status = approve(manager, second_server, 'mock.get_status')
            queue_plan(client, [step('echo', 'Use mock.echo to echo the supplied message.', criteria=[criterion('present', '/data')]), step('status', 'Use mock.get_status to read the integration fixture status.', criteria=[criterion('present', '/data')]), step('save', 'Save a report only after both observed results are verified.', kind='artifact', dependencies=['echo', 'status'])], [row('echo', echo['internal_id'], message='Explicit isolated parallelism probe.'), row('status', status['internal_id']), row('save', 'file.write', path='$artifact/report.txt', text='Observed provider results.')])
            key = fixture.submit('Use mock.echo and mock.get_status separately; preserve only verified observations.')
            fixture.await_state(key, 'awaiting_plan_approval')
            fixture.control(key, 'approve_plan')
            fixture.control(key, 'start')
            deadline = time.monotonic() + 4
            calls = []
            while not calls and time.monotonic() < deadline:
                calls = [dict(r, provider=label) for label, ledger in [('first', first_ledger), ('second', second_ledger)] for r in entries(ledger) if r['event'] == 'call']
                time.sleep(0.01)
            time.sleep(0.2)
            calls = [dict(r, provider=label) for label, ledger in [('first', first_ledger), ('second', second_ledger)] for r in entries(ledger) if r['event'] == 'call']
            observed = fixture.detail(key)
            evidence = {'calls_while_first_original_rpc_is_inflight': calls, 'step_states': {s['step_id']: s['status'] for s in observed['steps']}, 'worker_kinds': [w['kind'] for w in fixture.service.workers.values()], 'external_definitions': [echo['internal_id'], status['internal_id']], 'distinct_original_sdk_sessions': 2, 'declared_sdk_delay_seconds': 1.0, 'observation_wait_after_first_call_seconds': 0.2}
            from pathlib import Path
            (tmp_path / 'm3-imported-cross-session-evidence-cycle-1.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            assert len(calls) == 1, evidence
        finally:
            time.sleep(1.1)
            manager.close()

"""One campaign-owned original WorkflowService process; no OS/app restart."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from hanni.workflows.types import WorkflowLimits
from scripts.campaign4_boundaries.harness import QueuedStructuredClient, ServiceFixture, artifact_client, criterion, reviewed_start, step

def durable_json(path, data):
    path = Path(path)
    stage = path.with_name(path.name + '.publishing')
    with stage.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(stage, path)

def install_hash_fault(root):
    """Only the original file hash leaf fails once; handler identity stays original."""
    import hanni.tools.files as files
    from hanni.reliability.context import current_correlation_id
    original = files._sha256
    marker = root / 'hash-worker-failed.json'
    target = root / 'remaining-source.txt'

    def hash_leaf(path):
        if Path(path) == target and (not marker.exists()):
            durable_json(marker, dict(pid=os.getpid(), leaf='hanni.tools.files._sha256', source=target.name, correlation_id=current_correlation_id(), fault='controlled_TimeoutError'))
            raise TimeoutError('The owned fixture hash worker disconnected once.')
        return original(path)
    files._sha256 = hash_leaf
    return lambda: setattr(files, '_sha256', original)

def planned_client(root):
    first, second = (root / 'completed-source.txt', root / 'remaining-source.txt')
    client = QueuedStructuredClient()

    def outline(messages, _):
        data = json.loads(messages[1]['content'])
        report = Path(data['artifact_root']) / 'verified-report.txt'
        rows = [step('first_read', first)[0], step('hash_worker', second, capability='file.stat', dependencies=('first_read',), criteria=[criterion('/data/sha256', operator='nonempty')])[0], step('remaining_read', second, dependencies=('hash_worker',))[0], dict(step_id='save_report', description='Save the verified remaining source as a managed report.', kind='artifact', dependencies=['remaining_read'], required=True, criteria=[criterion('/data/path')]), step('readback_report', report, dependencies=('save_report',))[0]]
        return dict(summary='Controlled original-engine checkpoint/restart/report challenge.', unsupported_reason=None, steps=rows)

    def binding(messages, _):
        data = json.loads(messages[1]['content'])
        report = Path(data['artifact_root']) / 'verified-report.txt'
        return dict(unsupported_reason=None, steps=[step('first_read', first)[1], dict(step_id='hash_worker', capability_id='file.stat', arguments=dict(path=str(second), hash=True)), step('remaining_read', second)[1], dict(step_id='save_report', capability_id='file.write', arguments=dict(path=str(report), text={'$ref': dict(step_id='remaining_read', path='/data/text', type='string')})), dict(step_id='readback_report', capability_id='file.read', arguments=dict(path={'$ref': dict(step_id='save_report', path='/data/path', type='string')}))])
    client.enqueue(outline, binding)
    return client

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--phase', choices=('interrupt', 'recover'), required=True)
    parser.add_argument('--scenario', choices=('safe_checkpoint', 'ambiguous_before', 'ambiguous_after'), default='safe_checkpoint')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    marker = json.loads((root / 'challenge-owner.json').read_text(encoding='utf-8'))
    if marker.get('kind') != 'campaign4_owned_helper' or marker.get('root') != str(root):
        raise ValueError('This helper requires its parent-created owned challenge directory')
    import psutil
    process = psutil.Process()
    provenance = dict(pid=process.pid, parent_pid=process.ppid(), create_time=process.create_time(), executable=process.exe(), phase=args.phase, root=str(root))
    durable_json(root / (args.phase + '-worker-start.json'), provenance)
    safe = args.scenario == 'safe_checkpoint'
    restore = install_hash_fault(root) if safe else lambda: None
    box_holder = {}

    def observer(stage, receipt):
        if args.phase != 'interrupt' or safe:
            return
        box = box_holder['box']
        if stage == 'after_result':
            receipt = next((row for row in box.detail(box_holder['key'])['invocations'] if row['invocation_id'] == receipt['invocation_id']))
        if receipt.get('step_id') != 'save' or stage != ('before_dispatch' if args.scenario == 'ambiguous_before' else 'after_result'):
            return
        detail = box.detail(box_holder['key'])
        durable_json(root / 'interrupted.json', dict(pid=os.getpid(), provenance=provenance, workflow_id=box_holder['key'], detail=detail, lease=box.service.lease, controlled_model_calls=len(box.client.calls), stage=stage, termination='owned helper os._exit at uncertain original write boundary'))
        os._exit(83)
    try:
        client = (planned_client(root) if safe else artifact_client(root / 'completed-source.txt')) if args.phase == 'interrupt' else QueuedStructuredClient()
        with ServiceFixture(root / 'run', client=client, limits=WorkflowLimits(lease_seconds=1), observer=observer) as box:
            box_holder['box'] = box
            if args.phase == 'interrupt':
                key = box.submit('Read the exact completed source file ' + str(root / 'completed-source.txt') + ', hash and read the remaining source file ' + str(root / 'remaining-source.txt') + ', then save and reread its verified report.')
                box_holder['key'] = key
                reviewed_start(box, key)
                if not safe:
                    box.await_state(key, 'completed', 'blocked', timeout=8)
                    raise AssertionError('The owned write interruption was not reached')
                detail = box.service.wait(key, timeout=8, predicate=lambda row: any((item['kind'] == 'retry_scheduled' for item in row['checkpoints'])))
                first = next((item for item in detail['steps'] if item['step_id'] == 'first_read'))
                waiting = next((item for item in detail['steps'] if item['step_id'] == 'hash_worker'))
                assert first['status'] == 'verified' and first['attempts'] == 1
                assert waiting['status'] == 'pending' and waiting['attempts'] == 1
                assert not detail['active_uninterruptible']
                durable_json(root / 'interrupted.json', dict(pid=os.getpid(), workflow_id=key, provenance=provenance, detail=detail, lease=box.service.lease, controlled_model_calls=len(client.calls), termination='owned helper os._exit during committed retry backoff'))
                os._exit(83)
            original = json.loads((root / 'interrupted.json').read_text(encoding='utf-8'))
            key = original['workflow_id']
            initial = box.detail(key)
            if not safe:
                assert initial['status'] == 'blocked', initial
                assert box.service.lease['fence'] > original['lease']['fence']
                assert next((item for item in initial['steps'] if item['step_id'] == 'read'))['status'] == 'verified'
                assert any((item['step_id'] == 'save' and item['state'] == 'uncertain' for item in initial['invocations']))
                for operation in ('resume', 'retry_safe'):
                    from hanni.workflows.types import WorkflowError
                    try:
                        box.control(key, operation, **{'step_id': 'save'} if operation == 'retry_safe' else {})
                    except WorkflowError:
                        pass
                    else:
                        raise AssertionError('Uncertain write was admitted for replay')
                time.sleep(0.15)
                final = box.detail(key)
                assert len(final['invocations']) == len(original['detail']['invocations']) == 2
                assert not client.calls
                report = Path(next((item for item in final['steps'] if item['step_id'] == 'save'))['resolved_arguments']['path'])
                exists = report.exists()
                assert exists is (args.scenario == 'ambiguous_after')
                if exists:
                    assert report.read_text(encoding='utf-8') == (root / 'completed-source.txt').read_text(encoding='utf-8')
                durable_json(root / 'completed.json', dict(pid=os.getpid(), provenance=provenance, initial=initial, final=final, lease=box.service.lease, controlled_model_calls=0, report=dict(path=str(report), exists=exists, verified=False, sha256=hashlib.sha256(report.read_bytes()).hexdigest() if exists else None), no_automatic_or_explicit_replay=True))
                return
            assert initial['status'] == 'paused', initial
            assert box.service.lease['fence'] > original['lease']['fence']
            time.sleep(0.15)
            unchanged = box.detail(key)
            assert unchanged['status'] == 'paused'
            assert [item['invocation_id'] for item in unchanged['invocations']] == [item['invocation_id'] for item in original['detail']['invocations']]
            box.control(key, 'resume')
            final = box.await_state(key, 'completed', 'blocked', 'partially_completed', timeout=8)
            assert final['status'] == 'completed', final
            assert final['counts']['verified'] == 5 and len(final['invocations']) == 6
            first = next((item for item in final['steps'] if item['step_id'] == 'first_read'))
            assert first['attempts'] == 1
            before_id = next((item['invocation_id'] for item in original['detail']['invocations'] if item['step_id'] == 'first_read'))
            assert [item['invocation_id'] for item in final['invocations'] if item['step_id'] == 'first_read'] == [before_id]
            assert next((item for item in final['steps'] if item['step_id'] == 'hash_worker'))['attempts'] == 2
            assert len(client.calls) == 0, 'Persisted plans must not be replaced by replanning'
            report_step = next((item for item in final['steps'] if item['step_id'] == 'save_report'))
            report = Path(report_step['resolved_arguments']['path'])
            assert report.read_text(encoding='utf-8') == (root / 'remaining-source.txt').read_text(encoding='utf-8')
            assert all((item['verification']['status'] == 'VERIFIED' for item in final['steps']))
            durable_json(root / 'completed.json', dict(pid=os.getpid(), provenance=provenance, initial=initial, final=final, lease=box.service.lease, controlled_model_calls=len(client.calls), report=dict(path=str(report), sha256=hashlib.sha256(report.read_bytes()).hexdigest(), verification=report_step['verification'], independent_content_readback=True)))
    finally:
        restore()
if __name__ == '__main__':
    main()

"""Expose subsequent admission after a conservatively uncertain original write."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from hanni.workflows.types import WorkflowError
import hanni.tools.files as file_tools
from scripts.v3_review.service_fixture import ServiceFixture, QueuedStructuredClient

def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    src = Path('src/hanni/workflows/service.py')
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    rows = []
    for operation in ('resume', 'retry_safe'):
        root = output / operation
        root.mkdir()
        source = root / 'copper-specimen.txt'
        source.write_text('Independent copper specimen: 41 grams.', encoding='utf8')
        missing = root / 'late-observation.txt'
        missing.write_text('An independent optional hash observation.', encoding='utf8')
        original_hash = file_tools._sha256
        hash_attempts = []

        def hash_leaf(path):
            if operation == 'retry_safe' and Path(path) == missing and (not hash_attempts):
                hash_attempts.append('controlled_value_error')
                raise ValueError('The exposed original hash leaf is unavailable once.')
            return original_hash(path)
        file_tools._sha256 = hash_leaf
        steps = [dict(step_id='read', description='Read the text file ' + str(source), kind='tool', dependencies=[], required=True, criteria=[dict(operator='nonempty', path='/data/text', expected=None)])]
        if operation == 'retry_safe':
            steps.append(dict(step_id='optional', description='Check the SHA-256 hash of the file ' + str(missing), kind='tool', dependencies=['read'], required=False, criteria=[dict(operator='nonempty', path='/data/sha256', expected=None)]))
        for name in ('first', 'second'):
            steps.append(dict(step_id=name, description='Save the verified source text as ' + name + ' independent managed report.', kind='artifact', dependencies=['read'], required=True, criteria=[dict(operator='present', path='/data/path', expected=None)]))
        outline = dict(summary='Two independent controlled report copies, never an unknown-write replay.', unsupported_reason=None, steps=steps)

        def binding(messages, _):
            artifact = Path(json.loads(messages[1]['content'])['artifact_root'])
            specs = [dict(step_id='read', capability_id='file.read', arguments=dict(path=str(source)))]
            if operation == 'retry_safe':
                specs.append(dict(step_id='optional', capability_id='file.stat', arguments=dict(path=str(missing), hash=True)))
            for name in ('first', 'second'):
                specs.append(dict(step_id=name, capability_id='file.write', arguments=dict(path=str(artifact / (name + '.txt')), text={'$ref': dict(step_id='read', path='/data/text', type='string')})))
            return dict(unsupported_reason=None, steps=specs)
        holder, events = ({}, [])

        def observer(stage, receipt):
            if stage == 'before_dispatch' and receipt['step_id'] == 'first' and (not events):
                events.append(deepcopy(receipt))
                holder['fixture'].control(receipt['workflow_id'], 'pause')
        fixture = ServiceFixture(root / 'run', client=QueuedStructuredClient(outline, binding), observer=observer)
        holder['fixture'] = fixture
        try:
            fixture.observe('file.read', 'file.write', 'file.stat')
            fixture.start()
            key = fixture.submit('Read the text file ' + str(source) + ' and save its text in two independent managed reports.' + (' Optionally check the hash of file ' + str(missing) + '.' if operation == 'retry_safe' else ''))
            planned = fixture.await_state(key, 'awaiting_plan_approval', 'blocked', timeout=6)
            assert planned['status'] == 'awaiting_plan_approval', planned
            fixture.control(key, 'approve_plan')
            fixture.control(key, 'start')
            paused = fixture.await_state(key, 'paused', 'blocked', timeout=8)
            assert any((i['state'] == 'uncertain' and i['write'] for i in paused['invocations'])), paused
            assert fixture.ledger.entries('file.write') == 0
            missing.write_text('A later independently supplied safe read.', encoding='utf8')
            try:
                result = fixture.control(key, operation, **{'step_id': 'optional'} if operation == 'retry_safe' else {})
                control = dict(admitted=True, result=result)
            except WorkflowError as exc:
                control = dict(admitted=False, error_type=type(exc).__name__, message=str(exc))
            if control['admitted']:
                final = fixture.await_state(key, 'completed', 'partially_completed', 'blocked', 'paused', timeout=8)
            else:
                final = fixture.detail(key)
            writes = fixture.ledger.entries('file.write')
            paths = [p for p in fixture.service.artifacts_root.rglob('*.txt')]
            ids = [i['invocation_id'] for i in final['invocations']]
            rows.append(dict(operation=operation, passed=not control['admitted'] and writes == 0, control=control, paused=paused, final=final, actual_original_write_entries=writes, original_artifact_readbacks=[dict(name=p.name, text=p.read_text(encoding='utf8'), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths], unique_invocation_ids=len(ids) == len(set(ids)), observer_events=events, scope='Original service controls/approval and registry handlers; all actual writes confined to owned temporary reports. No model or owner action.'))
        finally:
            fixture.close()
            file_tools._sha256 = original_hash
    after = hashlib.sha256(src.read_bytes()).hexdigest()
    result = dict(source_before=before, source_after=after, source_unchanged=before == after, cases=rows, passed=sum((r['passed'] for r in rows)), total=len(rows))
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
    print(json.dumps([dict(operation=r['operation'], control_admitted=r['control']['admitted'], writes=r['actual_original_write_entries'], status=r['final']['status'], passed=r['passed']) for r in rows]))
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output)

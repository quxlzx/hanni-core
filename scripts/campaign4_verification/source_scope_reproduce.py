"""Literal owner-source objective retention, separate from original permission."""
import hashlib
import json
from pathlib import Path
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture

def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    src = Path('src/hanni/workflows/planner.py')
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    rows = []
    for variant in ('requested', 'substituted_outline', 'substituted_binding'):
        root = output / variant
        root.mkdir()
        requested = root / 'selected-sample.txt'
        requested.write_text('Independent selected sample: 27.', encoding='utf8')
        different = root / 'unrelated-sample.txt'
        different.write_text('Independent unrelated sample: 66.', encoding='utf8')
        described = different if variant == 'substituted_outline' else requested
        bound = different if variant in {'substituted_outline', 'substituted_binding'} else requested
        outline = dict(summary='Controlled source-copy plan.', unsupported_reason=None, steps=[dict(step_id='read', description='Read the text file ' + str(described), kind='tool', dependencies=[], required=True, criteria=[dict(operator='nonempty', path='/data/text', expected=None)]), dict(step_id='save', description='Save the verified predecessor text as a managed report.', kind='artifact', dependencies=['read'], required=True, criteria=[dict(operator='present', path='/data/path', expected=None)])])

        def binding(messages, _):
            artifact = Path(json.loads(messages[1]['content'])['artifact_root'])
            return dict(unsupported_reason=None, steps=[dict(step_id='read', capability_id='file.read', arguments=dict(path=str(bound))), dict(step_id='save', capability_id='file.write', arguments=dict(path=str(artifact / 'sample-report.txt'), text={'$ref': dict(step_id='read', path='/data/text', type='string')}))])
        fixture = ServiceFixture(root / 'run', client=QueuedStructuredClient(outline, binding))
        try:
            fixture.observe('file.read', 'file.write')
            fixture.start()
            key = fixture.submit('Read the text file ' + str(requested) + ' and save its exact contents as a managed report.')
            planned = fixture.await_state(key, 'awaiting_plan_approval', 'blocked', timeout=6)
            if planned['status'] == 'awaiting_plan_approval':
                fixture.control(key, 'approve_plan')
                fixture.control(key, 'start')
                final = fixture.await_state(key, 'completed', 'blocked', 'partially_completed', timeout=6)
            else:
                final = planned
            outputs = list(fixture.service.artifacts_root.rglob('sample-report.txt'))
            actual = [p.read_text(encoding='utf8') for p in outputs]
            rejected = final['status'] == 'blocked' and fixture.ledger.entries('file.read') == 0 and (fixture.ledger.entries('file.write') == 0)
            correct = final['status'] == 'completed' and actual == [requested.read_text(encoding='utf8')]
            rows.append(dict(variant=variant, passed=correct if variant == 'requested' else rejected or correct, objective_retained=correct, planning_rejected=rejected, status=final['status'], detail=final, actual_original_reads=fixture.ledger.entries('file.read'), actual_original_writes=fixture.ledger.entries('file.write'), observed_report_text=actual, scope='Literal source objective retention. The controlled owner reviewed every admitted proposal; wrong-source use is not asserted to bypass registry authorization. No semantic model quality is measured.'))
        finally:
            fixture.close()
    after = hashlib.sha256(src.read_bytes()).hexdigest()
    result = dict(source_before=before, source_after=after, source_unchanged=before == after, cases=rows, passed=sum((r['passed'] for r in rows)), total=len(rows))
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
    print(json.dumps([dict(variant=r['variant'], passed=r['passed'], status=r['status'], reads=r['actual_original_reads'], writes=r['actual_original_writes'], objective_retained=r['objective_retained']) for r in rows]))
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output)

"""Independent exposed control race; real service/registry, no owner resources."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from scripts.v3_review.service_fixture import ServiceFixture, QueuedStructuredClient

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = {str(p): digest(p) for p in Path('src/hanni/workflows').glob('*.py')}
    rows = []
    for operation in ('pause', 'cancel', 'none'):
        root = output / operation
        root.mkdir()
        source = root / 'quartz-reading.txt'
        source.write_text('Independent quartz exposure: 19 seconds.', encoding='utf8')
        outline = {'summary': 'Read the explicitly requested quartz measurement.', 'unsupported_reason': None, 'steps': [{'step_id': 'measure', 'description': 'Read the text file ' + str(source), 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'equals', 'path': '/data/text', 'expected': 'Independent quartz exposure: 19 seconds.'}]}]}
        binding = {'unsupported_reason': None, 'steps': [{'step_id': 'measure', 'capability_id': 'file.read', 'arguments': {'path': str(source)}}]}
        holder, triggers, controls = ({}, [], [])

        def observe(stage, data):
            if stage == 'before_dispatch' and (not triggers):
                triggers.append(deepcopy(data))
                if operation != 'none':
                    controls.append(holder['fixture'].control(data['workflow_id'], operation))
        fixture = ServiceFixture(root / 'state', client=QueuedStructuredClient(outline, binding), observer=observe)
        holder['fixture'] = fixture
        try:
            fixture.observe('file.read')
            fixture.start()
            key = fixture.submit('Inspect the quartz measurement in text file ' + str(source))
            planned = fixture.await_state(key, 'awaiting_plan_approval', 'blocked', timeout=6)
            assert planned['status'] == 'awaiting_plan_approval', planned
            fixture.control(key, 'approve_plan')
            fixture.control(key, 'start')
            expected = {'pause': 'paused', 'cancel': 'cancelled', 'none': 'completed'}[operation]
            final = fixture.await_state(key, expected, 'blocked', timeout=6)
            calls = fixture.ledger.entries('file.read')
            invocations = final['invocations']
            ids = [i['invocation_id'] for i in invocations]
            row = dict(operation=operation, expected_status=expected, observed_status=final['status'], passed=final['status'] == expected and calls == (1 if operation == 'none' else 0), actual_original_handler_entries=calls, consequential_writes=0, unique_invocation_ids=len(ids) == len(set(ids)), invocation_ids=ids, controls=controls, triggers=triggers, detail=final, original_source_file_unchanged=source.read_text(encoding='utf8') == 'Independent quartz exposure: 19 seconds.', scope='Original safe local read and owner control operations; scripted planner replies are protocol fixtures, never actual model quality.')
            rows.append(row)
        finally:
            fixture.close()
    after = {str(p): digest(p) for p in Path('src/hanni/workflows').glob('*.py')}
    result = dict(captured_at=datetime.now(timezone.utc).isoformat(), source_before=before, source_after=after, source_unchanged=before == after, cases=rows, passed=sum((r['passed'] for r in rows)), total=len(rows), actual_model_generation_http_requests=0, actual_owner_process_changes=0)
    path = output / 'results.json'
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'source_before', 'source_after', 'cases'}}))
    print(json.dumps([dict(operation=r['operation'], expected=r['expected_status'], observed=r['observed_status'], handler_entries=r['actual_original_handler_entries'], passed=r['passed']) for r in rows]))
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output)

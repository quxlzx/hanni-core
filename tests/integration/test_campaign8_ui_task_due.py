"""Compiled shipped helper through original isolated task update/readback."""
import json
from pathlib import Path
import subprocess
from uuid import uuid4
from scripts.campaign8_ui.backend import original_backend
from scripts.campaign8_ui.seed import populate_task_fidelity

def compiled_payloads(records):
    script = "\nimport fs from 'node:fs';\nimport ts from 'typescript';\nconst source = fs.readFileSync('src/task_due.ts','utf8');\nconst out = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;\nconst module = await import('data:text/javascript;base64,'+Buffer.from(out).toString('base64'));\nconst input = JSON.parse(fs.readFileSync(0,'utf8'));\nprocess.stdout.write(JSON.stringify(input.map(row=>module.taskDuePayload(row))));\n"
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=Path('frontend'), input=json.dumps(records), text=True, capture_output=True, timeout=15, check=True)
    return json.loads(result.stdout)

def test_compiled_payload_preserves_explicit_date_only_timed_and_missing():
    timed = '2026-11-03T14:25:00-05:00'
    assert compiled_payloads([{'due': '2026-11-03T00:00:00', 'all_day': True}, {'due': timed, 'all_day': False}, {'due': '', 'all_day': False}]) == ['2026-11-03', timed, None]

def test_compiled_update_payload_roundtrips_original_store_without_fabricated_flags(tmp_path):
    due_values = compiled_payloads([{'due': '2026-11-03T00:00:00', 'all_day': True}, {'due': '2026-11-03T14:25:00-05:00', 'all_day': False}])
    with original_backend(tmp_path / 'owned-fidelity') as backend:
        seeded = populate_task_fidelity(backend)
        for initial, due in zip(seeded['task_fidelity']['records'][:2], due_values):
            for status in ['completed', 'open']:
                _, actual = backend.request('/api/productivity')
                row = next((t for t in actual['tasks'] if t['id'] == initial['id']))
                body = {'id': str(uuid4()), 'operation': 'task.update', 'confirmed': True, 'data': {'task_id': row['id'], 'expected_fingerprint': row['fingerprint'], 'title': row['title'], 'course': row['course'], 'due': due, 'priority': row['priority'], 'project_id': row['project_id'], 'status': status}}
                code, _ = backend.request('/api/productivity', method='POST', body=body)
                assert code == 200
                _, actual = backend.request('/api/productivity')
                restored = next((t for t in actual['tasks'] if t['id'] == initial['id']))
                assert (restored['due'], restored['all_day']) == (initial['due'], initial['all_day'])
                assert restored['status'] == status
        assert backend.chat.ready is False
        assert all((call['outcome'] == 'CONTROLLED_UNAVAILABLE' for call in backend.calls))

import hashlib
import json
from pathlib import Path


def test_v4_only_appends_existing_workplace_tool_probes_to_unchanged_v3():
    root = Path(__file__).resolve().parents[2] / 'evals/llm_tools'
    manifest = json.loads((root / 'capability_coverage_v4_migration.json').read_text())
    before = (root / manifest['source']).read_bytes()
    after = (root / manifest['target']).read_bytes()
    assert hashlib.sha256(before).hexdigest() == manifest['source_sha256']
    assert hashlib.sha256(after).hexdigest() == manifest['target_sha256']
    assert after[:manifest['preserved_source_bytes']] == before
    added = [json.loads(row) for row in after[len(before):].splitlines()]
    assert [r['id'] for r in added] == manifest['added_case_ids']
    assert len(added) == 2 and all(r['required_tools'] == ['web.search'] for r in added)

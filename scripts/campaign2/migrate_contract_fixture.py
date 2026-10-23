"""Align only declared battery output keys in claim-free schema-only fixtures.

Preserve historical v1 and all v2 behavioral fields. This cannot tune prompts,
expected tool choices, inference answers or any sealed campaign holdout.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.evals.llm_coverage import DEFAULT_COVERAGE_CASES
from hanni.evals.routing import build_default_host

def sha(value):
    return hashlib.sha256(value).hexdigest()

def run():
    source = ROOT / DEFAULT_COVERAGE_CASES
    manifest = ROOT / 'evals/llm_tools/capability_coverage_v2_migration.json'
    historical = ROOT / 'evals/llm_tools/capability_coverage_v1.jsonl'
    original = source.read_bytes()
    original_manifest = manifest.read_bytes()
    historical_bytes = historical.read_bytes()
    document = json.loads(original_manifest)
    assert document['target_sha256'] == sha(original)
    archive = ROOT / 'data/campaign2-manager/contract-metadata-before'
    if archive.exists():
        raise ValueError('Do not overwrite preserved pre-migration evidence.')
    archive.mkdir(parents=True)
    (archive / source.name).write_bytes(original)
    (archive / manifest.name).write_bytes(original_manifest)
    rows = [json.loads(line) for line in original.decode('utf8').splitlines() if line.strip()]
    host = build_default_host()
    changes = []
    try:
        for row in rows:
            if row.get('fixture_scope') != 'schema_and_menu_only' or row.get('claims'):
                raise ValueError('Only claim-free schema fixtures may migrate.')
            primary = row['required_tools']
            if len(primary) != 1 or primary[0] not in {'system.battery', 'power.battery_detail'}:
                continue
            definition = host.registry.get(primary[0])
            before = deepcopy(row)
            data = row['results'][primary[0]]['data']
            additions = {'available': False} if primary[0] == 'system.battery' else {'present': False}
            assert set(definition.output_schema) - set(data) == set(additions)
            data.update(additions)
            assert set(data) == set(definition.output_schema)
            unchanged = deepcopy(row)
            unchanged['results'][primary[0]]['data'] = before['results'][primary[0]]['data']
            assert unchanged == before
            changes.append({'case_id': row['id'], 'capability_id': primary[0], 'added_schema_fields': additions, 'before': before['results'][primary[0]]['data'], 'after': deepcopy(data)})
            event = next((entry for entry in document['changes'] if entry['case_id'] == row['id']), None)
            fields = {'case_id': row['id'], 'primary_capability': primary[0], 'old_expected_schema': before['expected_schema'], 'new_expected_schema': row['expected_schema'], 'old_synthetic_data': {name: result['data'] for name, result in before['results'].items()}, 'new_synthetic_data': {name: result['data'] for name, result in row['results'].items()}}
            if event is None:
                document['changes'].append(fields)
            else:
                event['new_synthetic_data'] = fields['new_synthetic_data']
        if not changes:
            raise ValueError('No documented battery contract drift found.')
        target = ('\n'.join((json.dumps(row, ensure_ascii=True, separators=(',', ':')) for row in rows)) + '\n').encode('utf8')
        document['target_sha256'] = sha(target)
        document['changed_case_count'] = len(document['changes'])
        addendum = {'scope': 'Campaign 2 battery output contract metadata alignment', 'authorized_fields': ['results.system.battery.data.available', 'results.power.battery_detail.data.present'], 'changes': changes, 'before_target_sha256': sha(original), 'after_target_sha256': sha(target), 'historical_v1_sha256': sha(historical_bytes), 'behavioral_expectations_unchanged': True, 'reason': 'Declare observed availability/presence while preserving strict output-key drift checks. No actual provider result, prompt, required tool, answer claim, argument schema or risk metadata is changed.'}
        document.setdefault('metadata_addenda', []).append(addendum)
        assert historical.read_bytes() == historical_bytes
        source.write_bytes(target)
        manifest.write_text(json.dumps(document, ensure_ascii=True, indent=2) + '\n', encoding='utf8')
        (archive / 'addendum.json').write_text(json.dumps(addendum, indent=2) + '\n', encoding='utf8')
        print(json.dumps({'case_ids': [change['case_id'] for change in changes], 'behavioral_expectations_unchanged': True, 'historical_v1_unchanged': True, 'target_sha256': sha(target)}))
    finally:
        if host.registry.context.reliability:
            host.registry.context.reliability.close()
if __name__ == '__main__':
    run()

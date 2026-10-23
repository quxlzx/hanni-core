"""Version a schema-only corpus without changing any behavioral answer oracle.

The historical v1 file is never written. Only expected_schema and synthetic
result.data metadata can change. This is not the real-model sealed campaign or
the verifier's prospective rubric/cases. Strict coverage drift checks stay intact.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from hanni.evals.llm_coverage import fixture_for
from hanni.evals.routing import build_default_host

ROOT=Path(__file__).resolve().parents[2]


def migrate_unit_arguments():
    """Approved expected-schema-only addendum; no behavioral corpus change."""
    source=ROOT/'evals/llm_tools/capability_coverage_v2.jsonl'
    manifest=ROOT/'evals/llm_tools/capability_coverage_v2_migration.json'
    before=source.read_bytes()
    document=json.loads(manifest.read_text(encoding='utf-8'))
    assert hashlib.sha256(before).hexdigest()==document['target_sha256']
    archive=ROOT/'data/campaign1-engineering/unit-schema-migration-before'
    if archive.exists():raise ValueError('Preserve the first approved unit migration.')
    archive.mkdir(parents=True)
    (archive/source.name).write_bytes(before)
    (archive/manifest.name).write_bytes(manifest.read_bytes())
    rows=[json.loads(line) for line in before.decode('utf-8').splitlines() if line.strip()]
    host=build_default_host()
    changed=[]
    try:
        schema=host.registry.get('unit.convert').argument_schema()
        for row in rows:
            if row.get('required_tools')!=['unit.convert']:continue
            if row.get('fixture_scope')!='schema_and_menu_only' or row.get('claims'):
                raise ValueError('Only claim-free schema metadata may migrate.')
            old=deepcopy(row)
            row['expected_schema']=schema
            unchanged=deepcopy(row);unchanged['expected_schema']=old['expected_schema']
            assert unchanged==old
            if row==old:continue
            changed.append(row['id'])
            event=next((e for e in document['changes'] if e['case_id']==row['id']),None)
            if event is None:
                document['changes'].append({'case_id':row['id'],'primary_capability':'unit.convert',
                    'old_expected_schema':old['expected_schema'],'new_expected_schema':schema,
                    'old_synthetic_data':{n:r['data'] for n,r in old['results'].items()},
                    'new_synthetic_data':{n:r['data'] for n,r in row['results'].items()}})
            else:event['new_expected_schema']=schema
        if not changed:raise ValueError('No intentional unit schema drift was found.')
        output=('\n'.join(json.dumps(row,ensure_ascii=True,separators=(',',':')) for row in rows)+'\n').encode('utf-8')
        document['target_sha256']=hashlib.sha256(output).hexdigest()
        document['changed_case_count']=len(document['changes'])
        document.setdefault('metadata_addenda',[]).append({
            'scope':'Campaign 1 independently reproduced unit argument contract alignment',
            'authorized_fields':['unit.convert expected_schema only'],
            'case_ids':changed,'before_target_sha256':hashlib.sha256(before).hexdigest(),
            'after_target_sha256':document['target_sha256'],
            'behavioral_expectations_unchanged':True,
            'reason':'Required non-null unit fields and finite legal-unit descriptions; strict drift detection, numeric factors and all behavioral objectives retained.'})
        source.write_bytes(output)
        manifest.write_text(json.dumps(document,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    finally:
        if host.registry.context.reliability:host.registry.context.reliability.close()
    print(json.dumps({'changed_expected_schema_cases':changed,'all_other_case_fields_preserved':True,
                      'target_sha256':document['target_sha256']}))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-supplemental-addendum',action='store_true',help='Publish the manager-approved schema-only file.grep supplemental fixture; preserve initial migration evidence.')
    parser.add_argument('--approved-unit-argument-addendum',action='store_true',help='Migrate only manager-approved unit.convert argument metadata; preserve every behavioral field and the previous version.')
    args=parser.parse_args()
    if args.approved_unit_argument_addendum:
        if args.approved_supplemental_addendum:raise ValueError('Metadata addenda must be reviewed separately.')
        return migrate_unit_arguments()
    source=ROOT/'evals/llm_tools/capability_coverage_v1.jsonl'
    target=ROOT/'evals/llm_tools/capability_coverage_v2.jsonl'
    manifest=ROOT/'evals/llm_tools/capability_coverage_v2_migration.json'
    if target.exists() or manifest.exists():
        if not args.approved_supplemental_addendum:raise ValueError('Never overwrite a corpus version without the explicit approved metadata addendum.')
        archive=ROOT/'data/v36-engineering/coverage-migration-initial'
        archive.mkdir(parents=True,exist_ok=True)
        for original in (target,manifest):
            copy=archive/original.name
            if copy.exists():raise ValueError('Supplemental addendum was already published.')
            copy.write_bytes(original.read_bytes())
    before=source.read_bytes();rows=[json.loads(line) for line in before.decode('utf-8').splitlines() if line.strip()]
    host=build_default_host();migrated=[];changes=[];events=[]
    try:
        for original in rows:
            if original.get('fixture_scope')!='schema_and_menu_only' or original.get('claims'):
                raise ValueError('Migration is limited to schema/menu-only fixtures with no answer claims.')
            row=deepcopy(original)
            definitions=[host.registry.get(name) for name in row['required_tools']]
            if len(definitions)!=1:raise ValueError('Unexpected multiple-primary schema contract.')
            row['expected_schema']=definitions[0].argument_schema()
            for name,result in row.get('results',{}).items():
                shape=fixture_for(host.registry.get(name))['data']
                # Keep old synthetic values where the field still exists. The
                # corpus contains no claim/response oracle for these values.
                for key in shape:
                    if key in result['data']:
                        old=result['data'][key]
                        current=shape[key]
                        if current is None or type(old) is type(current):shape[key]=old
                result['data']=shape
            if args.approved_supplemental_addendum and row['id']=='COV-FILE-SEARCH-01':
                # Metadata wording exposed an additional read-only menu entry.
                # The requested/required file.search capability is unchanged;
                # this supplemental fixture supplies no answer claim or score.
                fixture=fixture_for(host.registry.get('file.grep'))
                row['results']['file.grep']=fixture
                events.append({'classification':'supplemental_schema_probe',
                    'case_id':row['id'],'capability_id':'file.grep','fixture':fixture,
                    'reason':'Current argument metadata adds a read-only file.grep menu alternative. Cover its schema without altering the original required file.search expectation, prompt, arguments or any behavioral oracle.',
                    'behavioral_expectations_unchanged':True})
            if row!=original:
                changes.append({'case_id':row['id'],'primary_capability':definitions[0].name,
                    'old_expected_schema':original['expected_schema'],'new_expected_schema':row['expected_schema'],
                    'old_synthetic_data':{n:r['data'] for n,r in original['results'].items()},
                    'new_synthetic_data':{n:r['data'] for n,r in row['results'].items()}})
            migrated.append(row)
        output=('\n'.join(json.dumps(row,ensure_ascii=True,separators=(',',':')) for row in migrated)+'\n').encode('utf-8')
        assert source.read_bytes()==before
        target.write_bytes(output)
        manifest.write_text(json.dumps({'version':2,'source':str(source.relative_to(ROOT)).replace('\\','/'),
            'target':str(target.relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(before).hexdigest(),
            'target_sha256':hashlib.sha256(output).hexdigest(),'case_count':len(rows),'changed_case_count':len(changes),
            'authorized_fields':['expected_schema','results.<capability>.data'],
            'unchanged':'All prompts, case IDs, required tools, acceptable alternatives, claims, risk/side-effect metadata, fixture messages and all behavioral expectations. Historical v1 bytes remain untouched. Strict drift detection retained.',
            'reason':'V3.6 independently reproduced truthful payload metadata and argument-schema repairs; migrate schema-only fixture metadata rather than weaken audit or alter frozen behavioral answers.',
            'changes':changes},ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
        document=json.loads(manifest.read_text(encoding='utf-8'))
        document['supplemental_schema_events']=events
        document['authorized_fields'].extend(['results.file.grep schema-only envelope in COV-FILE-SEARCH-01'] if events else [])
        manifest.write_text(json.dumps(document,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    finally:
        service=host.registry.context.reliability
        if service:service.close()
    print(json.dumps({'cases':len(rows),'changed_metadata_cases':len(changes),'v1_preserved':source.read_bytes()==before}))
    return 0


if __name__=='__main__':raise SystemExit(main())

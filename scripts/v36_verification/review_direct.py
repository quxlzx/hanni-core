"""Independently audit retained direct evidence, without replaying live effects.

Structural checks examine every merged record. Real retained file/ZIP/SQLite
artifacts are separately read where the operation leaves a durable artifact.
The verifier replayed all24 fixed desktop operations in a separate directory;
that stronger evidence is distinguished from this manager-run evidence review.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from hanni.config.loader import load_config
from hanni.tools import build_default_registry
from hanni.tools.base import ToolValidationError,ToolPermissionError,ToolRequest
from hanni.reliability.execution import close_service

ROOT=Path(__file__).resolve().parents[2]
SOURCES=['direct-cycle1','direct-harness-corrections','direct-repair-cycle2',
         'direct-spotify-volume-mock','direct-final-grounding','desktop-cycle2']
ISOLATED_ERRATA={'disk.folder_size','disk.largest_files','disk.largest_folders',
                 'power.battery_report','powershell.run','env.get','env.list','time.convert'}
TYPES={'array':list,'object':dict,'string':str,'boolean':bool,'integer':int,'number':(int,float),'null':type(None)}


def validate_contract(contract,data):
    problems=[]
    for key,kind in contract.items():
        optional='optional' in kind
        if key not in data:
            if not optional:problems.append('missing:'+key)
            continue
        options=kind.replace('optional ','').split('|')
        if all(k in TYPES for k in options):
            accepted=any(isinstance(data[key],TYPES[k]) and not(k in {'integer','number'} and isinstance(data[key],bool)) for k in options)
            if not accepted:problems.append('type:'+key)
    return problems


def artifact_review(name,row):
    args=row['input_request']; result=row.get('actual_response') or {}; data=result.get('data',{})
    checks=[]
    if name=='file.stat':
        target=Path(args['path']);assert target.is_file()
        assert data['sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
        assert data['size_bytes']==target.stat().st_size
        checks+=['actual retained file byte size/hash match']
    elif name=='file.read':
        assert data['text']==Path(args['path']).read_text(encoding='utf-8')
        checks+=['actual retained text bytes match']
    elif name=='file.head':
        assert data['lines']==Path(args['path']).read_text().splitlines()[:args['lines']]
        checks+=['actual retained first lines match']
    elif name=='file.tail':
        assert data['lines']==Path(args['path']).read_text().splitlines()[-args['lines']:]
        checks+=['actual retained last lines match']
    elif name=='file.write':
        assert Path(args['path']).read_text(encoding='utf-8')==args['text']
        checks+=['actual retained write content match']
    elif name=='file.move':
        assert not Path(args['source']).exists()
        assert Path(args['destination']).read_bytes()==Path(args['destination']).with_name('sample.txt').read_bytes()
        checks+=['source absent and actual retained moved bytes match']
    elif name=='file.copy':
        assert data['source_sha256']==hashlib.sha256(Path(args['source']).read_bytes()).hexdigest()
        later=Path(args['destination']).with_name('moved.txt')
        assert later.read_bytes()==Path(args['source']).read_bytes()
        checks+=['original copy commit receipt plus subsequent actual moved-copy bytes match; original copy destination intentionally moved later']
    elif name=='file.delete':
        assert not Path(args['path']).exists();checks+=['actual deleted fixture remains absent']
    elif name=='file.mkdir':
        assert Path(args['path']).is_dir();checks+=['actual created fixture directory exists']
    elif name=='file.grep':
        assert data['search_performed'] and data['match_count']==len(data['matches'])
        for match in data['matches']:
            assert args['query'] in Path(match['path']).read_text().splitlines()[match['line']-1]
        checks+=['every retained matched-file/line/content claim checked against actual bytes']
    elif name=='file.locate':
        assert all(Path(m['path']).is_file() and Path(m['path']).name==args['name'] for m in data['matches'])
        checks+=['every located fixture file exists with exact name']
    elif name=='archive.list':
        with ZipFile(args['archive']) as z:
            assert data['entry_count']==len(z.infolist())
        checks+=['actual ZIP entry count checked']
    elif name=='archive.zip':
        with ZipFile(args['destination']) as z:
            candidate=next(n for n in z.namelist() if Path(n).name=='sample.txt')
            assert z.read(candidate)==(Path(args['source'])/'sample.txt').read_bytes()
        checks+=['actual resulting ZIP contains exact controlled source bytes']
    elif name=='archive.unzip':
        with ZipFile(args['archive']) as z:
            assert (Path(args['destination'])/'sample.txt').read_bytes()==z.read('sample.txt')
        checks+=['actual extraction matches original ZIP bytes']
    elif name=='disk.largest_files':
        files=data['files'];assert files and Path(files[0]['path']).name=='data.bin'
        assert Path(files[0]['path']).stat().st_size>=max(Path(m['path']).stat().st_size for m in files)
        checks+=['retained largest-file ranking checked against actual fixture byte sizes']
    elif name=='power.battery_report':
        p=Path(args['destination']);assert p.is_file() and p.stat().st_size>1024
        assert '<html' in p.read_text(encoding='utf-8',errors='replace').casefold()
        checks+=['retained report is actual nonempty HTML; no private report content exported']
    elif name=='workspace.workspace.backup':
        p=ROOT/'data/v36-campaign/desktop-cycle2/state/workspace-backups'/result['backup_file']
        with sqlite3.connect(p) as db:assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        checks+=['actual retained SQLite backup passes quick_check']
    elif name=='project.test':
        assert data['exit_code']==0 and (Path(args['root'])/'verified.marker').read_text()=='cobalt lighthouse'
        checks+=['actual fixture test marker and original execution exit code match']
    elif name=='text.hash':
        assert data['digest']==hashlib.sha256(args['text'].encode()).hexdigest()
        checks+=['independent hashlib oracle matches exact text']
    elif name=='calc.evaluate':
        assert abs(data['value']-193.2)<1e-9;checks+=['independent arithmetic23%of840 oracle']
    return checks


def main():
    merged={}; hashes={}
    for name in SOURCES:
        path=ROOT/'data/v36-campaign'/name/'results.jsonl'
        raw=path.read_bytes();hashes[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
        for line in raw.decode().splitlines():
            row=json.loads(line);row['_evidence_source']=str(path.relative_to(ROOT));merged[row['capability_id']]=row
    assert len(merged)==196
    replay_path=ROOT/'data/v36-verification/desktop-operations-cycle1/results.jsonl'
    replay={r['capability_id']:r for r in map(json.loads,replay_path.read_text().splitlines())}
    descriptors=json.loads((ROOT/'data/v36-campaign/desktop-cycle2/inventory.json').read_text())['capabilities']
    desktop={d['id']:d for d in descriptors}
    rows=[]
    with TemporaryDirectory(dir=ROOT/'data/v36-verification',prefix='direct-schema-audit-') as tmp:
        config=load_config(ROOT/'config',data_dir=Path(tmp),env={})
        registry=build_default_registry(config)
        try:
            assert {d.name for d in registry.definitions()}==set(merged)-set(desktop)
            for name,row in sorted(merged.items()):
                observed=row['outcome'];errors=[];checks=[]
                if name in desktop:
                    negative=row['negative_cases']
                    assert {n['exception_type'] for n in negative}=={'ToolValidationError','ToolPermissionError'}
                    assert replay[name]['outcome']=='ISOLATED_PASS'
                    assert {n['exception_type'] for n in replay[name]['negative_cases']}=={'ToolValidationError','ToolPermissionError'}
                    checks+=['independent original operation replay valid/readback and invalid/chat-profile refusal']
                    method='INDEPENDENT_REPLAY_AND_RETAINED_EVIDENCE_REVIEW'
                else:
                    definition=registry.get(name)
                    definition.validate_arguments(row['input_request'])
                    try:definition.validate_arguments({'v36_unexpected_field':True})
                    except ToolValidationError:pass
                    else:raise AssertionError('Current validator admitted unknown argument')
                    if observed=='BLOCKED':
                        # The initial journal stores negatives only after a
                        # successful ordinary call. Preserve that omission;
                        # replay only the denial, which cannot dispatch a tool.
                        try:registry.execute(ToolRequest(name,row['input_request'],actor_profile='everyone_else'))
                        except ToolPermissionError:pass
                        else:raise AssertionError('Blocked dependency tool exposed to chat-only profile')
                        checks+=['original blocked journal omits negative receipt fields; independent pure validator and original chat-only denial replayed without handler dispatch']
                    else:
                        assert row['invalid_result']['exception_type']=='ToolValidationError'
                        assert row['permission_result']['exception_type']=='ToolPermissionError'
                        checks+=['current original argument validator independently checked; retained invalid/profile receipts match']
                    if observed!='BLOCKED':
                        assert row['actual_response']['ok'] is True and not row['contract_errors']
                        errors=validate_contract(definition.output_schema,row['actual_response']['data'])
                        assert not errors,(name,errors)
                        checks+=['actual recorded result conforms to current per-operation declared output fields/types']
                    else:
                        assert name in {'project.lint','project.format'}
                        assert 'not installed' in row['failure']
                        checks+=['actual optional dependency unavailable; preserved BLOCKED, no installation or fake response']
                    method='INDEPENDENT_RETAINED_EVIDENCE_AND_SCHEMA_REVIEW'
                    if observed=='BLOCKED':method+='; INDEPENDENT_BLOCKED_NEGATIVE_GATE_REPLAY'
                artifacts=artifact_review(name,row)
                if artifacts:method+='; INDEPENDENT_RETAINED_ARTIFACT_READBACK'
                if name in ISOLATED_ERRATA and observed=='LIVE_PASS':observed='ISOLATED_PASS'
                reason='; '.join(checks+artifacts)
                if observed=='MOCK_PASS':
                    reason+='; consequential OS/provider dependency leaves mocked, original registry/handler executed; live effect not demonstrated'
                elif observed=='LIVE_PASS':
                    reason+='; changing live observation reviewed at recorded receipt scope, no second time sample treated as same moment or every live value independently measured'
                elif observed=='ISOLATED_PASS':
                    reason+='; controlled input/state only, no production-data or live provider success credit'
                entry={'capability_id':name,'verification_status':'INDEPENDENTLY_REVIEWED_SCOPED_EVIDENCE',
                       'method':method,'evidence':[row['_evidence_source']],
                       'reason':reason,'outcome':observed,'original_outcome':row['outcome'],
                       'schema_errors':errors,'independent_checks':checks+artifacts,
                       'live_effect_replayed':False,'actual_model_inference_by_this_review':False}
                if name in desktop:
                    entry['evidence'].append(str(replay_path.relative_to(ROOT)))
                    entry['isolated_operation_replayed']=True
                rows.append(entry)
        finally:close_service(Path(tmp))
    result={'rows':rows,'evidence_source_hashes':hashes,
            'summary':{'capabilities':len(rows),'outcomes':dict(Counter(r['outcome'] for r in rows)),
                       'independent_desktop_replays':24,'independent_retained_artifact_readbacks':sum('ARTIFACT_READBACK' in r['method'] for r in rows),
                       'no_additional_live_effect_replays':True,
                       'disclosure':'Evidence/schema audit of all196, not independent live reenactment of all196. Focused independent tests and24 isolated desktop replays are separate artifacts; imported MCP reviewed separately.'}}
    output=ROOT/'data/v36-verification/direct-evidence-review.json'
    assert not output.exists(),'Preserve original independent review'
    output.write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=True))


if __name__=='__main__':main()

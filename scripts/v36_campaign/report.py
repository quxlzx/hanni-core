"""Export reviewed, non-sensitive inventory/coverage; retain raw evidence privately."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry


def read(path,default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def journal(path):
    if not path.exists():return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def normalize_direct(row):
    value=dict(row)
    # Classification corrections describe the real fixture, not changed results.
    name=row['capability_id']
    if row['environment_type']=='live' and name in {
        'disk.folder_size','disk.largest_files','disk.largest_folders','power.battery_report',
        'powershell.run','env.get','env.list','time.convert'}:
        value['classification_erratum']='Original artifact used LIVE for controlled synthetic inputs; original raw evidence retained.'
        value['environment_type']='isolated'
        if value['outcome']=='LIVE_PASS':value['outcome']='ISOLATED_PASS'
    return value


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'docs/v36')
    p.add_argument('--phase',default='M7_REPAIRS_AND_INDEPENDENT_VERIFICATION')
    options=p.parse_args()
    output=options.output.resolve()
    assert output.is_relative_to(ROOT/'docs')
    output.mkdir(parents=True,exist_ok=True)
    config=load_config(ROOT/'config',data_dir=ROOT/'data/v36-campaign/report-state',env={})
    registry=build_default_registry(config)
    try:
        inventory=[dict(id=d.name,description=d.description,input_schema=d.argument_schema(),
            output_contract=dict(d.output_schema),domain=d.name.split('.')[0],
            permission_level=d.permission_level,risk_level=d.risk_level,side_effect=d.side_effect,
            confirmation_policy='Always explicit' if d.risk_level>=3 else 'Argument dependent' if d.requires_confirmation_if else 'Normal profile policy',
            required_dependencies=list(d.prerequisites),dependency_metadata_scope='Declared registry prerequisites; observed external/hardware blockers are recorded under availability and the final subsystem report.',handler_module=d.handler.__module__,origin='default_registry')
            for d in registry.definitions()]
    finally:registry.context.reliability.close()
    extra=read(ROOT/'data/v36-campaign/desktop-cycle2/inventory.json',{'capabilities':[]})['capabilities']
    known={x['id'] for x in inventory}
    inventory.extend(row for row in extra if row['id'] not in known)
    direct={}
    batches=['direct-cycle1','direct-harness-corrections','direct-repair-cycle2',
             'direct-spotify-volume-mock','direct-final-grounding','desktop-cycle2']
    for batch in batches:
        path=ROOT/'data/v36-campaign'/batch/'results.jsonl'
        for row in journal(path):
            row=normalize_direct(row)
            row['evidence_artifact']=str(path.relative_to(ROOT)).replace('\\','/')
            direct[row['capability_id']]=row
    model={row['capability_id']:row for row in journal(ROOT/'data/v36-engineering/model-outputs-v2.jsonl')}
    reviewed=read(ROOT/'data/v36-verification/baseline-response-scores.json',{'rows':[]})
    quality={row['capability_id']:row for row in reviewed['rows']}
    desktop_reviewed=read(ROOT/'data/v36-verification/private-desktop-response-scores.json',{'rows':[]})
    quality.update({row['capability_id']:row for row in desktop_reviewed['rows']})
    independent=read(ROOT/'data/v36-verification/direct-evidence-review.json',{'rows':[]})
    independent_by_id={row['capability_id']:row for row in independent['rows']}
    rows=[];ledger=[]
    for definition in sorted(inventory,key=lambda x:x['id']):
        name=definition['id'];a=direct.get(name);b=model.get(name);q=quality.get(name)
        if a is None:
            status='BLOCKED';reason='No completed direct journal; implementation coverage still incomplete.'
        else:status=a['outcome'];reason=a.get('failure')
        live={'outcome':'BLOCKED','reason':'External provider is synthetic; live credentials/API remain unverified.'} if name.startswith(('google','gmail.','email.')) else {
            'outcome':'UNSAFE_TO_RUN' if a and a.get('live_status')=='UNSAFE_TO_RUN' else
                      'LIVE_PASS' if a and a['environment_type']=='live' and status=='LIVE_PASS' else 'BLOCKED',
            'reason':'Consequential or private OS dependency is simulated; no live side effect authorized.' if a and a.get('live_status')=='UNSAFE_TO_RUN' else 'Direct evidence environment: '+(a['environment_type'] if a else 'unavailable')}
        if b:
            measured=b.get('selection_measurement')=='MEASURED'
            selection={'case_id':b['case_id'],'outcome':('ISOLATED_PASS' if b.get('operation_equivalent_selected') else 'FAIL') if measured else 'BLOCKED',
                'original_policy_eligible':b['original_policy_eligible'],'exact_selected':b.get('exact_capability_selected'),
                'prospective_alias_selected':b.get('operation_equivalent_selected'),'model_menu_measured':b.get('selection_measurement'),
                'actual_model_inferences':b.get('inference_requests'),
                'evidence_artifact':'data/v36-engineering/model-outputs-v2.jsonl',
                'scope':b.get('model_evaluation_scope')}
            argument_score=q.get('components',{}).get('accurate_tool_arguments') if q else None
            argument={'outcome':q['outcome'] if measured and q else 'BLOCKED','rubric_component':argument_score,
                      'maximum':1.5,'outcome_scope':'Independent end-to-end case outcome; argument correctness is scored separately, without inventing a binary threshold.',
                      'reason':q.get('reason') if q else 'Independent scoring unavailable'}
        else:
            selection={'outcome':'BLOCKED','reason':'Fixed desktop registry is not exposed to the conversational controller; explicit UI confirmation is required.',
                       'actual_model_inferences':q.get('actual_inference_requests') if q else None,
                       'scope':'Actual response-only diagnostic; no private tool menu or execution authority.'}
            argument={'outcome':'BLOCKED','reason':selection['reason']}
        response={'outcome':q['outcome'],'score':q['rubric_score'],'components':q['components'],
                  'reason':q['reason'],'evidence_artifact':'data/v36-verification/baseline-response-scores.json' if b else 'data/v36-verification/private-desktop-response-scores.json',
                  'quality_gate_scope':'Original baseline controller cohort' if b else 'Response-only conditional diagnostic, not full controller quality acceptance',
                  'verification_method':q['verification_method']} if q else {'outcome':'BLOCKED','reason':selection.get('reason','No independent response score')}
        final=status
        if (q and q['outcome']=='FAIL') or selection['outcome']=='FAIL': final='FAIL'
        elif live['outcome']=='UNSAFE_TO_RUN':final='UNSAFE_TO_RUN'
        elif selection['outcome']=='BLOCKED' or response['outcome']=='BLOCKED':final='BLOCKED'
        row={**definition,'availability':live,'direct_execution_test':{
            'outcome':status,'environment':a['environment_type'] if a else None,
            'negative_argument_test':'PASS' if (a and (a.get('invalid_result') or a.get('negative_cases'))) or 'INDEPENDENT_BLOCKED_NEGATIVE_GATE_REPLAY' in independent_by_id.get(name,{}).get('method','') else 'BLOCKED',
            'permission_rejection_test':'PASS' if (a and (a.get('permission_result') or a.get('negative_cases'))) or 'INDEPENDENT_BLOCKED_NEGATIVE_GATE_REPLAY' in independent_by_id.get(name,{}).get('method','') else 'BLOCKED',
            'verification_status':independent_by_id.get(name,{}).get('verification_status',a.get('verification_status') if a else 'INCOMPLETE'),
            'independent_evidence':independent_by_id.get(name),
            'latency_seconds':a.get('latency_seconds') if a else None,'reason':reason,
            'evidence_artifact':a.get('evidence_artifact') if a else None},
            'model_selection_test':selection,'argument_generation_test':argument,
            'response_quality_test':response,
            'verification_method':'Original registry gates plus isolated artifact/readback or dependency-boundary simulation; separate independent response review.',
            'final_result':final,'final_result_scope':'All evaluated baseline layers. Post-repair checks remain separate; baseline model scores are not retroactively promoted.'}
        rows.append(row)
        if final in {'FAIL','BLOCKED','UNSAFE_TO_RUN'} or (q and q.get('critical_scope_failure')):
            ledger.append({'capability_id':name,'final_outcome':final,'direct_outcome':status,
                'direct_failure':reason,'response_outcome':response['outcome'],'response_score':response.get('score'),
                'reason':response.get('reason') or live['reason'],
                'critical_mock_scope_failure':q.get('critical_scope_failure') if q else False,
                'repair_status':'See independently verified defect ledger; unchanged original model scores are retained.'})
    coverage={'phase':options.phase,'registered_default':len(inventory)-len(extra),'registered_fixed_desktop':len(extra),
        'total_registered_union':len(rows),'accounted_for':len(rows),
        'inventory_origin':'Current build_default_registry() descriptors plus actual fixed desktop operation registry; transient local MCP imports reported separately.',
        'runtime_snapshot_scope':'196 is the observed union across actual default/private-desktop test registries. The fresh screenshot-only cycle5 registry contains 172 because its fixed desktop mutations were not invoked; 24 private operations register lazily.',
        'independent_direct_summary':independent.get('summary'),
        'direct_outcomes':dict(Counter(x['direct_execution_test']['outcome'] for x in rows)),
        'final_baseline_layer_outcomes':dict(Counter(x['final_result'] for x in rows)),
        'model_baseline':read(ROOT/'data/v36-engineering/model-baseline-summary.json'),
        'independent_response_summary':reviewed.get('summary'),
        'private_desktop_diagnostic_summary':desktop_reviewed.get('summary'),
        'final_unseen_response_summary':read(ROOT/'data/v36-verification/fresh-response-scores.json',{}).get('summary'),
        'post_cohort_source_addendum':'A later general calendar activity/morphology and numeric stored-body guard repair passed independent46 tests and the original legacy corpus. Frozen24 model results were not regenerated and are pre-addendum quality evidence.',
        'final_regression_summary':read(ROOT/'data/v36-campaign/final-regression-summary.json'),
        'mechanical_core_review':read(ROOT/'data/v36-verification/core-workflow-review.json'),
        'actual_persistent_workflow_summary':read(ROOT/'data/v36-verification/actual-workflow-review.json',{}).get('summary'),
        'limitations':['Mock provider success does not prove live cloud integration.',
            'Direct success does not prove correct model selection or grounded responses.',
            'Baseline model failures remain even when a subsequent production defect repair passes.',
            'No acoustic/vision/LAYA model pass is inferred from logic mocks or configuration.'],
        'rows':rows}
    (output/'capability-inventory.json').write_text(json.dumps(coverage,indent=2,ensure_ascii=True),encoding='utf-8')
    (output/'failure-ledger.json').write_text(json.dumps({'phase':options.phase,'rows':ledger},indent=2,ensure_ascii=True),encoding='utf-8')
    lines=['# V3.6 capability coverage','',f"Current registry union: **{len(rows)}** ({len(inventory)-len(extra)} default, {len(extra)} fixed desktop).",
        '','Each direct classification describes the implementation environment. Model selection and response quality are separate. Original model baseline failures are retained after repair. Live risk and external-provider blockers remain explicit in the machine inventory.',
        '','| Capability | Direct | Model selection | Response /10 | Baseline final |',
        '| --- | --- | --- | ---: | --- |']
    for row in rows:
        score=row['response_quality_test'].get('score')
        lines.append(f"| `{row['id']}` | {row['direct_execution_test']['outcome']} | {row['model_selection_test']['outcome']} | {score if score is not None else 'Blocked'} | {row['final_result']} |")
    lines.extend(['','Detailed schemas, gates, dependencies, evidence references and reasons: [machine inventory](capability-inventory.json).',
                  'Unresolved baseline defects and explicit live restrictions: [failure ledger](failure-ledger.json).'])
    (output/'CAPABILITY_COVERAGE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Export scores and reasons, never raw responses, messages or tool arguments.
    score_fields={'capability_id','case_id','test_id','outcome','components','rubric_score','reason',
                  'verification_method','original_policy_eligible','selection_measurement',
                  'actual_request_completed','actual_requested_data_or_action_completed',
                  'expected_handling_passed','measured_model_tool_menu','appropriate_selection',
                  'critical_scope_failure','critical_unauthorized_execution','latency_ms'}
    cohorts={}
    for label,path in [('baseline','baseline-response-scores.json'),('final_unseen','fresh-response-scores.json'),
                       ('private_desktop_response_only','private-desktop-response-scores.json'),
                       ('temporary_local_mcp','external-mcp-response-scores.json')]:
        raw=read(ROOT/'data/v36-verification'/path,{})
        cohorts[label]={'summary':raw.get('summary'),
                       'cohort_sha256':raw.get('prospective_cohort_sha256'),
                       'rows':[{k:v for k,v in row.items() if k in score_fields} for row in raw.get('rows',[])]}
    (output/'RESPONSE_SCORES.json').write_text(json.dumps(cohorts,indent=2,ensure_ascii=True),encoding='utf-8')
    imported=read(ROOT/'data/v36-engineering/actual-external-mcp-cycle4/inventory.json',{'capabilities':[]})
    imported_review=read(ROOT/'data/v36-verification/external-mcp-response-scores.json',{'rows':[]})
    imported_scores={r['capability_id']:r for r in imported_review['rows']}
    imported_execution={r['case']['capability_id']:r for r in journal(ROOT/'data/v36-engineering/actual-external-mcp-cycle4/results.jsonl')}
    imported_rows=[]
    for definition in imported['capabilities']:
        name=definition['name'];q=imported_scores.get(name,{});execution=imported_execution.get(name,{})
        imported_rows.append({'id':name,'description':definition['description'],
            'input_schema':definition['argument_schema'],'output_contract':definition['output_contract'],
            'domain':'mcp','risk_level':definition['risk_level'],'permission_level':definition['permission_level'],
            'confirmation_policy':definition['confirmation_policy'],'required_dependencies':['Temporary local SDK stdio test server'],
            'origin':'Actual approved temporary MCP registry import',
            'availability':{'outcome':'BLOCKED','reason':'Temporary local integration server is intentionally closed after the campaign; it is not configured in production.'},
            'direct_execution_test':{'outcome':q.get('direct_outcome','BLOCKED'),
                                    'invalid_fields_rejected':bool(execution.get('direct_invalid',{}).get('rejected')) and execution.get('invalid_dispatched') is False,
                                    'verification_method':q.get('verification_method'),'evidence':q.get('evidence')},
            'model_selection_test':{'outcome':'ISOLATED_PASS' if q.get('model_selection_measured') and q.get('tool_selected') else 'BLOCKED',
                                    'scope':'Original configured controller menu; write policy is unchanged'},
            'argument_generation_test':{'rubric_component':q.get('components',{}).get('accurate_tool_arguments'),'maximum':1.5},
            'response_quality_test':{'outcome':q.get('outcome','BLOCKED'),'score':q.get('rubric_score'),'components':q.get('components'),'reason':q.get('reason')},
            'final_result':q.get('outcome','BLOCKED')})
    (output/'MCP_CAPABILITIES.json').write_text(json.dumps({'scope':'Three actual temporary SDK imports, separate from the 196 observed default/private-desktop union and current production runtime.',
        'summary':imported_review.get('summary'),'rows':imported_rows},indent=2,ensure_ascii=True),encoding='utf-8')
    native=read(ROOT/'data/v36-verification/native-scores.json')
    if native is not None:
        (output/'NATIVE_SCORES.json').write_text(json.dumps(native,indent=2,ensure_ascii=True),encoding='utf-8')
    print(json.dumps({key:value for key,value in coverage.items() if key in {'phase','total_registered_union','accounted_for','direct_outcomes','final_baseline_layer_outcomes'}},ensure_ascii=True))


if __name__=='__main__':main()

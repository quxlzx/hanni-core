"""Project metadata-only observed registry calls onto the original capability list.

No capability executes here. Historical menus/static references remain distinct
from handler-entry and returned evidence. A failed suite is labelled explicitly.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations',type=Path,required=True)
    parser.add_argument('--real-reads',type=Path,help='Separate coordinator read-only Windows smoke artifact; never inferred from profiling.')
    parser.add_argument('--workflows',type=Path,help='Frozen candidate controlled workflow artifact.')
    parser.add_argument('--live-results',type=Path,help='Completed actual-model results with controlled read-only adapters.')
    parser.add_argument('--model-arguments',type=Path,help='Post-run original-schema structural audit mapped by capability ID.')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    baseline=ROOT/'docs/reliability-reviews/baseline-capability-coverage.csv'
    with baseline.open(encoding='utf8',newline='') as stream:rows=list(csv.DictReader(stream))
    evidence=json.loads(args.observations.read_text(encoding='utf8'))
    indexed={}
    for item in evidence['observations']:indexed.setdefault(item['capability_id'],[]).append(item)
    real_reads={}
    if args.real_reads:
        smoke=json.loads(args.real_reads.read_text(encoding='utf8'))
        if smoke.get('passed') is not True or not isinstance(smoke.get('checks'),list):
            raise ValueError('Real-read evidence must contain a passing explicit checks array')
        for check in smoke['checks']:
            identifier=check.get('capability_id')
            if identifier not in {'time.now','system.stats','process.top_memory','process.top_cpu'} or identifier in real_reads:
                raise ValueError('Unexpected or repeated real-read evidence identity')
            real_reads[identifier]=check
    workflows=json.loads(args.workflows.read_text(encoding='utf8'))['results'] if args.workflows else []
    live=json.loads(args.live_results.read_text(encoding='utf8'))['results'] if args.live_results else []
    arguments=json.loads(args.model_arguments.read_text(encoding='utf8'))['calls'] if args.model_arguments else []
    for row in rows:
        samples=indexed.get(row['capability_id'],[])
        entered=[item for item in samples if item['handler_entered']]
        builtin=[item for item in entered if item['handler_origin']=='production_builtin']
        controlled=[item for item in entered if item['handler_origin']=='fixture_or_other']
        row.update(observed_production_handler_entries=sum(item['count'] for item in builtin),
            observed_controlled_handler_entries=sum(item['count'] for item in controlled),
            observed_denied_or_prehandler_returns=sum(item['count'] for item in samples if not item['handler_entered']),
            observed_evidence_scopes=';'.join(sorted({item['verification_scope'] for item in entered if item['verification_scope']!='unknown'})),
            observed_evidence_statuses=';'.join(sorted({item['verification_status'] for item in entered if item['verification_status']!='unknown'})),
            observed_evidence_methods=';'.join(sorted({item['verification_method'] for item in entered if item['verification_method']!='unknown'})),
            runtime_evidence=('PRODUCTION_CODE_CONTROLLED_TEST_DEPENDENCIES' if builtin else
                'CONTROLLED_HANDLER_ONLY' if controlled else 'NO_HANDLER_ENTRY_OBSERVED'),
            source_suite_exitstatus=evidence['exitstatus'],real_adapter_or_hardware_success='NOT_ESTABLISHED_BY_PROFILER')
        smoke_check=real_reads.get(row['capability_id'])
        row.update(real_local_read_smoke=('COORDINATOR_OBSERVED_PASS' if smoke_check and
            smoke_check.get('response_ok') is True and smoke_check.get('evidence_valid') is True else 'NOT_OBSERVED'),
            real_local_read_evidence_scope=(smoke_check.get('verification',{}).get('scope','unknown') if smoke_check else ''),
            real_local_read_source_scope=('FINAL_RUNTIME_SHA_'+smoke['runtime_manifest']['sha256'] if smoke_check and smoke.get('runtime_manifest')
                else 'Separate Windows smoke; runtime source hash absent from artifact' if smoke_check else ''))
        identifier=row['capability_id']
        containing=[case for case in workflows if identifier in case['actual_tools']]
        tool_results=[result for case in containing for result in case['tool_results'] if result['capability']==identifier]
        model_calls=[call for case in live for call in case['calls'] if call['name']==identifier]
        structural=[call for call in arguments if call.get('capability_id')==identifier]
        row.update(workflow_registry_request_cases=len(containing),
            workflow_controlled_handler_entries=sum(call['capability']==identifier for case in workflows for call in case['handler_calls']),
            workflow_successful_registry_returns=sum(result['ok'] for result in tool_results),
            workflow_verification_scopes=';'.join(sorted({result['verification_scope'] for result in tool_results if result.get('verification_scope')})),
            workflow_verification_statuses=';'.join(sorted({result['verification_status'] for result in tool_results if result.get('verification_status')})),
            workflow_scope='CONTROLLED_MODEL_AND_PROVIDER_GENUINE_ISOLATED_LOCAL_STORES' if containing else 'NOT_OBSERVED',
            actual_model_raw_calls=len(structural),actual_model_schema_valid_calls=sum(call['schema_valid'] for call in structural),
            actual_model_adapter_entries=len(model_calls),actual_model_successful_adapter_returns=sum(call['ok'] for call in model_calls),
            actual_model_scope='ACTUAL_INFERENCE_CONTROLLED_READ_ONLY_ADAPTERS' if structural or model_calls else 'NOT_OBSERVED')
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/'capability-coverage.csv'
    with path.open('w',encoding='utf8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    observed={row['capability_id'] for row in rows if int(row['observed_production_handler_entries']) or int(row['observed_controlled_handler_entries'])}
    builtin={row['capability_id'] for row in rows if int(row['observed_production_handler_entries'])}
    controlled={row['capability_id'] for row in rows if int(row['observed_controlled_handler_entries'])}
    report={'capability_count':len(rows),'observed_any_handler':len(observed),'observed_production_code':len(builtin),
        'observed_controlled_handler':len(controlled),'no_handler_entry_observed':len(rows)-len(observed),
        'outside_original_capability_list':sorted(set(indexed)-{row['capability_id'] for row in rows}),
        'suite_exitstatus':evidence['exitstatus'],'observer_errors':evidence['observer_errors'],
        'observations_sha256':hashlib.sha256(args.observations.read_bytes()).hexdigest(),
        'original_matrix_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
        'real_reads_sha256':hashlib.sha256(args.real_reads.read_bytes()).hexdigest() if args.real_reads else None,
        'real_local_read_observed':sum(row['real_local_read_smoke']=='COORDINATOR_OBSERVED_PASS' for row in rows),
        'real_reads_runtime_sha256':smoke.get('runtime_manifest',{}).get('sha256') if args.real_reads else None,
        'workflow_sha256':hashlib.sha256(args.workflows.read_bytes()).hexdigest() if args.workflows else None,
        'live_results_sha256':hashlib.sha256(args.live_results.read_bytes()).hexdigest() if args.live_results else None,
        'workflow_capability_request_observed':sum(bool(row['workflow_registry_request_cases']) for row in rows),
        'actual_model_capability_adapter_observed':sum(bool(row['actual_model_adapter_entries']) for row in rows),
        'limits':['Python original-registry execution frames only; direct handler calls and subprocesses excluded.',
            'Production code may use injected or mocked dependencies; no assertion of real provider/hardware success.',
            'No raw arguments, prompts, messages or result bodies stored.',
            'Historical menu/static-reference columns remain historical, not execution evidence.',
            'A failing source suite is preserved as evidence, not described as final regression acceptance.']}
    (args.output/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='outside_original_capability_list'}))

if __name__=='__main__':main()

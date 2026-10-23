"""Aggregate frozen outcomes without giving compiled plans or early blocks credit."""
import collections
import hashlib
import json
import math
from pathlib import Path


def percentiles(values):
    values = sorted(v for v in values if v is not None)
    if not values: return {'n': 0, 'p50': None, 'p95': None}
    def at(p):
        index = (len(values)-1)*p; low = int(index)
        return values[low]+(values[min(low+1,len(values)-1)]-values[low])*(index-low)
    return {'n':len(values), 'p50':at(.5), 'p95':at(.95)}


def failure(record):
    detail = record.get('detail') or {}
    if record.get('false_completion'): return 'objective_coverage_false_completion'
    if record.get('positive_pass'): return 'verified_positive'
    if record.get('exception'): return 'harness_or_timeout'
    invocations = detail.get('invocations', [])
    if invocations:
        if any((i.get('result') or {}).get('ok') is False for i in invocations): return 'execution'
        if any(s.get('status') == 'unverified' for s in detail.get('steps', [])): return 'verification'
    reason = detail.get('error') or ''
    if 'routed menu' in reason: return 'retrieval_or_admission'
    if 'Planning is blocked' in reason: return 'model_declared_unsupported_not_proof_of_missing_capability'
    if 'invalid bounded' in reason or 'omitted' in reason or 'valid bounded plan' in reason: return 'model_planning_validation'
    return 'compilation_or_policy_validation'


def main():
    root = Path('data/phase2')
    frozen = json.loads(Path('evals/phase2/freeze.json').read_text())
    for name, digest in frozen.items():
        assert hashlib.sha256((Path('evals/phase2')/name).read_bytes()).hexdigest()==digest
    rows = json.loads((root/'heldout-final.json').read_text())['records']
    assert len(rows)==40
    cases = {c['id']:c for c in json.loads(Path('evals/phase2/heldout.json').read_text())}
    positives = [r for r in rows if r.get('positive', True)]
    negatives = [r for r in rows if not r.get('positive', True)]
    families = {}
    for family in ('performance','authorized_file','report'):
        group = [r for r in positives if cases[r['id']]['family']==family]
        families[family] = {'passed':sum(r['positive_pass'] for r in group),'total':len(group)}
    # A substring in a model's unsupported reason cannot prove a boundary hit.
    actual_boundaries = [r['id'] for r in negatives if r.get('negative_boundary_reached')
                        and not (r.get('detail',{}).get('error') or '').startswith('Planning is blocked:')]
    invalid_boundary_credits = [r['id'] for r in negatives if r.get('negative_boundary_reached') and r['id'] not in actual_boundaries]
    writes = []
    unauthorized = 0
    duplicates = 0
    for r in rows:
        detail = r.get('detail') or {}
        seen = set()
        for invocation in detail.get('invocations', []):
            if not invocation['write']: continue
            writes.append({'case':r['id'],'capability':invocation['capability_id'],'state':invocation['state']})
            approved = any(a['kind']=='action' and a['state']=='consumed'
                           and a['approval_id']==invocation.get('approval_id') for a in detail['approvals'])
            plan_review = detail.get('scope',{}).get('provenance')=='owner_plan_review'
            unauthorized += int(not cases[r['id']].get('report') or not (approved or plan_review))
            effect = (invocation['capability_id'],invocation['argument_hash'])
            duplicates += int(effect in seen);seen.add(effect)
    def timings(path):
        records = json.loads(path.read_text())['records']
        return {'terminal_or_approval_boundary_ms':percentiles([r.get('total_ms') for r in records]),
                'validated_goal_completion_ms':percentiles([r.get('total_ms') for r in records if r.get('positive_pass')]),
                'model_call_ms':percentiles([c['duration_ms'] for r in records for c in r.get('model_calls',[])])}
    summary = {'status':'PHASE_2_NOT_ACCEPTED', 'freeze':frozen,
        'positive_passed':sum(r['positive_pass'] for r in positives),'positive_total':len(positives),
        'families':families,'false_completions':[r['id'] for r in rows if r.get('false_completion')],
        'actual_negative_boundaries':actual_boundaries,'negative_total':len(negatives),
        'invalid_raw_boundary_credits_discarded':invalid_boundary_credits,
        'negative_safe_blocks_without_boundary_credit':len(negatives)-len(actual_boundaries),
        'unauthorized_writes_in_live_harness':unauthorized,'duplicate_writes_in_live_harness':duplicates,
        'live_writes':writes,'positive_failure_breakdown':dict(collections.Counter(failure(r) for r in positives)),
        'case_outcomes':[{'id':r['id'],'positive':r.get('positive',True),'passed':r['positive_pass'],
                         'classification':failure(r),'error':(r.get('detail') or {}).get('error'),
                         'verified_steps':(r.get('detail') or {}).get('counts',{}).get('verified',0)} for r in rows],
        'before':timings(root/'baseline/development-live-final.json'),
        'after_development':timings(root/'development-measured-final.json'),
        'heldout':timings(root/'heldout-final.json'),
        'speech':'NOT TESTED physical speech/acoustic onset','server_queue':'NOT MEASURED',
        'provider':'NOT TESTED live calendar provider; absent-vault seam',
        'recovery_scope':'Scripted planners and injected failures through original registry plus actual owned process-crash integration tests; not model intelligence evidence.'}
    if (root/'phase1-responsiveness.json').exists():
        previous = json.loads(Path('data/phase1/development-after.json').read_text())
        current = json.loads((root/'phase1-responsiveness.json').read_text())
        summary['phase1_responsiveness_regression'] = {
            'before_phase1_checkpoint':previous['latency'], 'after_current_phase2_candidate':current['latency'],
            'sample_sizes':[len(previous['records']),len(current['records'])], 'paired':False,
            'simple_development_success_before':previous['simple_task_success'],
            'simple_development_success_after':current['simple_task_success'],
            'brevity_before':previous['brevity'],'brevity_after':current['brevity']}
    if (root/'regressions.json').exists():
        summary['regressions'] = json.loads((root/'regressions.json').read_text())
    (root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('positive_passed','positive_total','families','false_completions','actual_negative_boundaries','positive_failure_breakdown','before','after_development','heldout')},indent=2))


if __name__=='__main__': main()

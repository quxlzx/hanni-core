"""Map actual original store fault receipts and native reached edges separately."""
import json
from pathlib import Path
from hanni.workflows.types import TRANSITIONS

def build(cohort_root, post_persist_root):
    cohort_root, post_persist_root = (Path(cohort_root), Path(post_persist_root))
    summary = json.loads((cohort_root / 'summary.json').read_text(encoding='utf-8'))
    pre = {(row['source'], row['target']): row for row in summary['transitions']}
    post_summary = json.loads((post_persist_root / 'results.json').read_text(encoding='utf-8'))
    post = {(row['source'], row['target']): row for row in post_summary['receipts']}
    native = {(row['source'], row['target']): row for row in summary['native_transition_coverage']}
    rows = []
    for source, targets in sorted(TRANSITIONS.items()):
        for target in sorted(targets):
            edge = (source, target)
            rows.append({'source': source, 'target': target, 'direct_stale_CAS_fault': {'passed': pre.get(edge, {}).get('passed', False), 'receipt': str(cohort_root / 'summary.json'), 'scope': 'original_store_commit_boundary'}, 'direct_postprojection_checkpoint_fault': {'passed': post.get(edge, {}).get('passed', False), 'receipt': str(post_persist_root / 'results.json'), 'scope': 'original_store_sqlite_transaction_rollback'}, 'native_scheduler': {'cases': native.get(edge, {}).get('cases', []), 'reachability': 'REACHED' if native.get(edge, {}).get('cases') else 'UNREACHED', 'transition_specific_before_and_after_fault_proof': 'NOT_ESTABLISHED_BY_THIS_REACHABILITY_TRACE'}})
    return {'edges': len(rows), 'rows': rows, 'store_pre_fault_pass': sum((r['direct_stale_CAS_fault']['passed'] for r in rows)), 'store_post_fault_pass': sum((r['direct_postprojection_checkpoint_fault']['passed'] for r in rows)), 'native_reached': sum((r['native_scheduler']['reachability'] == 'REACHED' for r in rows)), 'native_unreached': sum((r['native_scheduler']['reachability'] == 'UNREACHED' for r in rows))}
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('cohort')
    parser.add_argument('postpersist')
    parser.add_argument('output')
    args = parser.parse_args()
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = build(args.cohort, args.postpersist)
    destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}, indent=2))

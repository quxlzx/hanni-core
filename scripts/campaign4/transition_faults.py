"""Prospective after-write/before-checkpoint SQLite faults on every declared edge.

The original Store.update writes its projection, then its checkpoint, inside
one original transaction. A TEMP SQLite trigger aborts checkpoint insertion.
This is direct durable transaction coverage, not native scheduler reachability.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from hanni.workflows.store import WorkflowStore
from hanni.workflows.types import TRANSITIONS, fingerprint

def seal(path):
    cases = [{'source': source, 'target': target, 'boundary': 'after_projection_before_checkpoint', 'expected': 'sqlite_abort_with_no_record_or_checkpoint_change'} for source, targets in sorted(TRANSITIONS.items()) for target in sorted(targets)]
    raw = json.dumps(cases, indent=2, sort_keys=True).encode() + b'\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError('Prospective transition faults already frozen')
    path.write_bytes(raw)
    return (cases, hashlib.sha256(raw).hexdigest())

def route_to(source):
    queue, visited = ([('submitted', [])], set())
    while queue:
        state, route = queue.pop(0)
        if state == source:
            return route
        if state in visited:
            continue
        visited.add(state)
        queue.extend(((target, route + [target]) for target in sorted(TRANSITIONS.get(state, ()))))
    return None

def run(output, sealed='evals/workflows/campaign4_transition_faults.json'):
    cases, digest = seal(sealed)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    from scripts.campaign4.run_cohort import production_manifest
    source_before = production_manifest()
    (output / 'source-before.json').write_text(json.dumps(source_before, indent=2), encoding='utf-8')
    receipts = []
    for case in cases:
        store = WorkflowStore(output / 'fixtures' / (case['source'] + '-' + case['target']))
        receipt = {**case, 'scope': 'direct_original_store_sqlite_leaf_fault', 'passed': False}
        try:
            record = store.create('Isolated checkpoint atomicity after projection persistence', 'assisted')
            path = route_to(case['source'])
            if path is None:
                receipt['classification'] = 'BLOCKED_UNREACHABLE_GRAPH'
                continue
            for state in path:
                record = store.update(record['workflow_id'], record['revision'], {'status': state})
            key = record['workflow_id']
            before = {'record': store.get(key), 'history': store.history(key)}
            store._connect().execute("CREATE TEMP TRIGGER campaign_checkpoint_abort BEFORE INSERT ON main.checkpoints BEGIN SELECT RAISE(ABORT, 'campaign injected checkpoint fault'); END")
            rejected = False
            try:
                store.update(key, record['revision'], {'status': case['target']}, kind='after_projection_fault')
            except sqlite3.IntegrityError as exc:
                receipt['error'] = str(exc)
                rejected = True
            finally:
                store._connect().execute('DROP TRIGGER temp.campaign_checkpoint_abort')
            after = {'record': store.get(key), 'history': store.history(key)}
            store.close()
            reopened = {'record': store.get(key), 'history': store.history(key)}
            receipt.update(rejected=rejected, before_hash=fingerprint(before), after_hash=fingerprint(after), reopened_hash=fingerprint(reopened), passed=rejected and before == after == reopened)
        except Exception as exc:
            receipt['harness_error'] = {'type': type(exc).__name__, 'message': str(exc)}
        finally:
            receipts.append(receipt)
            store.close()
    summary = {'cases': len(cases), 'passed': sum((r['passed'] for r in receipts)), 'sealed_sha256': digest, 'receipts': receipts, 'scope': 'all dynamically declared edges, direct store after SQL projection/before checkpoint fault; native coverage separate'}
    source_after = production_manifest()
    summary['source_uniform'] = source_before == source_after
    (output / 'source-after.json').write_text(json.dumps(source_after, indent=2), encoding='utf-8')
    (output / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    print(json.dumps(run(parser.parse_args().output), indent=2))

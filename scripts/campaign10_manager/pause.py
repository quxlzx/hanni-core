"""Durable read-only closeout: preserve public evidence and unopened final holdout."""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import zipfile
from scripts.campaign8_manager.preflight import digest, runtime
from scripts.campaign9_manager.integrity import dependencies, identity
from scripts.campaign10_verification.integrity import snapshot_source
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign10-manager/pause-checkpoint'

def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8')

def quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * p
    lo = math.floor(index)
    hi = math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)

def live_metrics():
    base = ROOT / 'data/campaign10-manager/live-core-cycle1'
    summary = json.loads((base / 'SUMMARY.json').read_text(encoding='utf8'))
    wire = json.loads((base / 'model/WIRE.json').read_text(encoding='utf8'))
    usage = []
    durations = []
    tool_menu_tasks = set()
    for row in wire:
        if row.get('finished_at') is not None:
            durations.append((row['finished_at'] - row['started_at']) * 1000)
        if row['request_body'].get('tools'):
            tool_menu_tasks.add(row['task_id'])
        raw = row.get('raw_response', '')
        found = None
        try:
            found = json.loads(raw).get('usage')
        except (ValueError, AttributeError):
            for line in raw.splitlines():
                if line.startswith('data:'):
                    try:
                        event = json.loads(line[5:].strip())
                        if isinstance(event, dict) and event.get('usage'):
                            found = event['usage']
                    except ValueError:
                        pass
        if isinstance(found, dict):
            usage.append(found)
    rows = summary['rows']
    tasks = [r['duration_ms'] for r in rows if r.get('duration_ms') is not None]
    return {'tasks': len(rows), 'generation_posts': len(wire), 'tasks_with_posts': sum((r.get('actual_model_calls', 0) > 0 for r in rows)), 'original_actual_generated_true': sum((r.get('actual_generated') is True for r in rows)), 'tasks_exposed_nonempty_model_menu': len(tool_menu_tasks), 'http_statuses': dict(Counter((str(r.get('status')) for r in wire))), 'task_latency_samples': len(tasks), 'task_p50_ms': quantile(tasks, 0.5), 'task_p95_ms': quantile(tasks, 0.95), 'generation_latency_samples': len(durations), 'generation_p50_ms': quantile(durations, 0.5), 'generation_p95_ms': quantile(durations, 0.95), 'usage_receipts': len(usage), 'observed_prompt_tokens': sum((x.get('prompt_tokens', 0) for x in usage)), 'observed_completion_tokens': sum((x.get('completion_tokens', 0) for x in usage)), 'usage_scope': 'Only returned usage objects; missing usage is not assigned zero.', 'semantic_accuracy': 'NOT_MEASURED; untouched independent final is unrun', 'scope_caveats': ['Early blank-root file.search enumerated common owner folders, returned zero matches/no content.', 'Original deterministic shortcuts are not model tool selection.', 'Control fixture values/prerequisites were not uniformly active in this actual-session cohort.', 'Some tasks require more than the fixed three-generation budget.', '34 original generated flags differ from 35 tasks with observed POSTs; wire is authoritative.']}

def main():
    if OUT.exists():
        raise FileExistsError('Preserve the durable checkpoint.')
    OUT.mkdir(parents=True)
    before = json.loads((ROOT / 'data/campaign10-manager/PREFLIGHT.json').read_text(encoding='utf8'))
    changed = [p for p, h in before['source_manifest'].items() if not (ROOT / p).is_file() or digest(ROOT / p) != h]
    protected = [p for p, h in before['protected'].items() if not (ROOT / p).is_file() or digest(ROOT / p) != h]
    observed = runtime()
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'status': 'PAUSED_BY_USER_BEFORE_FINAL', 'baseline_source_files': len(before['source_manifest']), 'changed_preexisting_sources': changed, 'protected_files_compared': len(before['protected']), 'changed_prior_campaign_evidence': protected, 'owner_backend_model_identities_unchanged': identity(before['runtime']) == identity(observed), 'native_artifact_unchanged': digest(ROOT / before['native_artifact']['path']) == before['native_artifact']['sha256'], 'runtime': observed, 'owned_acceptance_origin': 'http://127.0.0.1:8766', 'owned_acceptance_closed': not any((c.status == 'LISTEN' and c.laddr.port == 8766 for c in __import__('psutil').net_connections(kind='tcp'))), 'owner_database_comparison': 'NOT_MEASURED; owner memory databases not opened or mounted.', 'private_holdout_inspected': False, 'final_tasks': 45, 'final_executed': 0, 'final_GO_issued': False, 'original_source_archive_sha256': digest(ROOT / 'data/campaign10-manager/original-source.zip')}
    write(OUT / 'PRESERVATION.json', receipt)
    write(OUT / 'LIVE_METRICS.json', live_metrics())
    inventory = json.loads((ROOT / 'data/campaign10-manager/INVENTORY.json').read_text(encoding='utf8'))
    prior = json.loads((ROOT / 'docs/campaign2/INVENTORY.json').read_text(encoding='utf8'))
    current_ids = {r['id'] for r in inventory}
    previous_ids = {r['id'] for r in prior['builtins']}
    write(OUT / 'INVENTORY_COVERAGE.json', {'current_registered': len(current_ids), 'enumerated': len(inventory), 'mapped_to_C2': len(current_ids & previous_ids), 'new_default_ids': sorted(current_ids - previous_ids), 'removed_default_ids': sorted(previous_ids - current_ids), 'scope': 'Fresh default registry172 and normal isolated actual controller; C2 tests are historical, not rerun live passes.', 'controlled_lifetime_registry_union': 179, 'distinct_controlled_handler_ids': 35, 'additional_tools_scope': 'Lazy workspace and one inert external MCP tool in disposable test registries.'})
    freeze = snapshot_source(ROOT)
    write(OUT / 'SOURCE_MANIFEST.json', freeze)
    write(OUT / 'DEPENDENCIES.json', dependencies())
    with zipfile.ZipFile(OUT / 'SOURCE.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for row in freeze['files']:
            archive.write(ROOT / row['path'], row['path'])
    write(OUT / 'CHECKPOINT.json', {'at': receipt['at'], 'status': receipt['status'], 'source_sha256': freeze['source_sha256'], 'source_manifest_sha256': digest(OUT / 'SOURCE_MANIFEST.json'), 'source_files': freeze['file_count'], 'archive_sha256': digest(OUT / 'SOURCE.zip'), 'dependencies_sha256': digest(OUT / 'DEPENDENCIES.json'), 'private_final_seal_sha256': digest(ROOT / 'docs/campaign10/FINAL_SEAL.json'), 'held_source_unchanged_after_archive': snapshot_source(ROOT)['files'] == freeze['files'], 'acceptance': 'NOT_COMPLETED; final45 untouched; no GO issued', 'resume_handoff': 'docs/campaign10/CONTINUATION.md'})
    print(json.dumps({'checkpoint': OUT.relative_to(ROOT).as_posix(), 'source_files': freeze['file_count'], 'preexisting_changes': len(changed), 'prior_evidence_changes': len(protected), 'owner_unchanged': receipt['owner_backend_model_identities_unchanged'], 'owned_closed': receipt['owned_acceptance_closed'], 'final_executed': 0}))
    if changed or protected or (not receipt['owner_backend_model_identities_unchanged']) or (not receipt['owned_acceptance_closed']):
        raise RuntimeError('Checkpoint integrity requires review; do not advance final.')
if __name__ == '__main__':
    main()

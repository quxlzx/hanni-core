"""Oracle-free final wrapper. Dispatch belongs to original public service adapters."""
import json
from pathlib import Path
import time
import traceback
from .contracts import contained_path, normalize_receipt, receipt_observation, validate_case
from .integrity import assert_freeze, claim_once, digest, verify_go

def run_input(case, case_root, executor):
    case = validate_case(case)
    case_root = Path(case_root).resolve()
    case_root.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    try:
        raw = executor(case, case_root)
    except Exception as exc:
        raw = {'id': case['id'], 'evidence_categories': ['NOT_RUN'], 'adapter_error': {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}, 'actions': [], 'request_path_original': False}
    try:
        raw.setdefault('duration_ms', (time.perf_counter() - started) * 1000)
        return normalize_receipt(case, raw)
    except Exception as exc:
        failed = {'id': case['id'], 'evidence_categories': ['NOT_RUN'], 'adapter_error': {'type': type(exc).__name__, 'message': str(exc)}, 'raw_adapter_receipt': raw, 'request_path_original': False, 'duration_ms': (time.perf_counter() - started) * 1000}
        return normalize_receipt(case, failed)

def collect_once(repo, private_root, freeze_path, go_path, executor):
    """Collect every sealed task once; execution never reads the oracle file."""
    repo, private_root = (Path(repo).resolve(), Path(private_root).resolve())
    if not private_root.is_relative_to(repo / 'data' / 'campaign10-verifier'):
        raise ValueError('Private collection must belong to the verifier disposable root.')
    seal = json.loads((private_root / 'SEAL.json').read_text(encoding='utf-8'))
    inputs = private_root / 'inputs.json'
    if digest(inputs) != seal['input_sha256']:
        raise ValueError('Untouched input hash mismatch.')
    cases = json.loads(inputs.read_text(encoding='utf-8'))['cases']
    for case in cases:
        validate_case(case)
    if len(cases) != seal['task_count'] or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Task identity/count changed after sealing.')
    freeze = json.loads(Path(freeze_path).read_text(encoding='utf-8'))
    source_hash = assert_freeze(repo, freeze)
    go = json.loads(Path(go_path).read_text(encoding='utf-8'))
    verify_go(go, source_hash, seal['input_sha256'])
    claim_once(private_root / 'FINAL_ATTEMPT.json', {'state': 'COLLECTION_CLAIMED', 'source_sha256': source_hash, 'input_sha256': seal['input_sha256'], 'go_nonce': go['nonce']})
    run_root = private_root / 'final-once'
    run_root.mkdir(exist_ok=False)
    records = []
    for index, case in enumerate(cases, 1):
        root = contained_path(run_root, f'case-{index:03d}')
        row = run_input(case, root, executor)
        row['source_sha256'] = source_hash
        target = run_root / f'receipt-{index:03d}.json'
        target.write_text(json.dumps(receipt_observation(row), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        records.append({'id': case['id'], 'receipt': target.name, 'sha256': digest(target)})
    final_source = assert_freeze(repo, freeze)
    manifest = {'version': 1, 'task_count': len(cases), 'source_sha256': final_source, 'input_sha256': seal['input_sha256'], 'records': records, 'collection_complete': True}
    target = run_root / 'MANIFEST.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return {'task_count': len(cases), 'source_sha256': source_hash, 'manifest_sha256': digest(target), 'collection_complete': True}

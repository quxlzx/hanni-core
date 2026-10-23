"""Source-byte snapshot and once-only oracle-free independent workflow holdout."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import zipfile
from .executor import PRIVATE, ROOT, digest, durable, run_case

def source_manifest():
    files = set((ROOT / 'src').rglob('*.py'))
    files.update((ROOT / 'config').rglob('*.yaml'))
    files.add(ROOT / 'pyproject.toml')
    files.add(ROOT / '.gitattributes')
    files.add(ROOT / 'tests/helpers.py')
    for pattern in ('scripts/campaign4*', 'tests/integration/test_campaign4*'):
        for entry in ROOT.glob(pattern):
            if entry.is_dir():
                files.update(entry.rglob('*.py'))
            elif entry.suffix == '.py':
                files.add(entry)
    files.update((ROOT / 'scripts/v3_review').glob('*.py'))
    files.update(ROOT.glob('docs/campaign4/*PROTOCOL*.md'))
    files.update((path for path in (ROOT / 'evals/workflows').glob('campaign4*.json') if not path.name.endswith(('_results.json', '_coverage.json'))))
    for directory in ('tests/unit', 'tests/integration'):
        files.update((ROOT / directory).glob('test_campaign4*.py'))
        files.update((ROOT / directory).glob('test_workflow*.py'))
    files.update({ROOT / 'tests/unit/test_dashboard_workflows.py', ROOT / 'tests/unit/test_email_workflow_reliability.py'})
    files.update({ROOT / 'scripts/campaign1_verification/recording.py', ROOT / 'scripts/campaign3_manager/model_probe.py'})
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(files)}

def snapshot(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    proof = {'captured_at': datetime.now(timezone.utc).isoformat(), 'files': source_manifest()}
    with zipfile.ZipFile(output / 'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, expected in proof['files'].items():
            raw = (ROOT / name).read_bytes()
            import hashlib
            if hashlib.sha256(raw).hexdigest() != expected:
                raise RuntimeError('Source changed during snapshot')
            archive.writestr(name, raw)
    proof['archive_sha256'] = digest(output / 'source.zip')
    durable(output / 'proof.json', proof)
    return proof

def check_seal():
    holdout = PRIVATE / 'holdout'
    seal = json.loads((holdout / 'seal.json').read_text(encoding='utf8'))
    if any((digest(holdout / name) != expected for name, expected in seal['hashes'].items())):
        raise RuntimeError('Private sealed input or oracle bytes changed')
    return seal

def run_final(proof_path, output):
    """Manager explicit source-freeze permission is an external prerequisite."""
    proof_path, output = (Path(proof_path).resolve(), Path(output).resolve())
    if not output.is_relative_to(PRIVATE):
        raise ValueError('Final evidence must stay private')
    if not sys.pycache_prefix or not Path(sys.pycache_prefix).resolve().is_relative_to(PRIVATE):
        raise ValueError('Use a fresh private -X pycache_prefix for the frozen run')
    seal = check_seal()
    proof = json.loads(proof_path.read_text(encoding='utf8'))
    frozen = proof.get('files', proof.get('manifest'))
    if frozen != source_manifest():
        raise RuntimeError('The complete current source/config/harness proof differs')
    claim = PRIVATE / 'holdout-final-claim.json'
    with claim.open('x', encoding='utf8') as stream:
        json.dump({'started_at': datetime.now(timezone.utc).isoformat(), 'output': str(output), 'status': 'once_only_started', 'proof_sha256': digest(proof_path), 'seal_sha256': digest(PRIVATE / 'holdout/seal.json'), 'planned_cases': seal['case_count']}, stream, indent=2)
    cases = [json.loads(line) for line in (PRIVATE / 'holdout/cases.jsonl').read_text(encoding='utf8').splitlines()]
    if len(cases) != seal['case_count']:
        raise RuntimeError('Sealed planned denominator differs')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    completed = []
    for case in cases:
        check_seal()
        if source_manifest() != frozen:
            durable(output / 'ABORT.json', {'reason': 'source_changed', 'completed': completed, 'not_tested': len(cases) - len(completed)})
            raise RuntimeError('Source changed; remaining final cases NOT TESTED')
        path = output / 'receipts' / (case['id'] + '.json')
        try:
            receipt = run_case(case, output / 'fixtures' / case['id'])
        except Exception as exc:
            receipt = {'id': case['id'], 'category': case['category'], 'scenario': case['scenario'], 'harness_error': {'type': type(exc).__name__, 'message': str(exc)}, 'actual_model_calls': 0}
        durable(path, receipt)
        completed.append({'id': case['id'], 'category': case['category'], 'receipt': path.relative_to(output).as_posix(), 'receipt_sha256': digest(path), 'execution_state': 'fixture_or_execution_error' if receipt.get('harness_error') else 'executed'})
        durable(output / 'PROGRESS.json', {'completed': completed, 'planned': len(cases), 'actual_model_calls': 0, 'elapsed_seconds': time.monotonic() - started})
        print(json.dumps({'completed': len(completed), 'planned': len(cases), 'errors': sum((row['execution_state'] != 'executed' for row in completed))}), flush=True)
    durable(output / 'COMPLETE.json', {'completed': completed, 'planned': len(cases), 'source_unchanged': source_manifest() == frozen, 'seal_unchanged': check_seal() == seal, 'proof_sha256': digest(proof_path), 'elapsed_seconds': time.monotonic() - started, 'pycache_prefix': sys.pycache_prefix, 'once_only': True})

def publish(run, output):
    from .scoring import score_run
    run, output = (Path(run).resolve(), Path(output).resolve())
    summary = score_run(run, PRIVATE / 'holdout')
    complete = json.loads((run / 'COMPLETE.json').read_text(encoding='utf8'))
    summary['source_unchanged'] = complete['source_unchanged']
    summary['sealed_inputs_unchanged'] = complete['seal_unchanged']
    summary['once_only'] = complete['once_only']
    summary['elapsed_seconds'] = complete['elapsed_seconds']
    summary['receipt_provenance'] = {'private_run': run.relative_to(ROOT).as_posix(), 'summary_sha256': digest(run / 'SUMMARY.json'), 'grades_sha256': digest(run / 'GRADES.json'), 'complete_sha256': digest(run / 'COMPLETE.json'), 'seal_sha256': digest(PRIVATE / 'holdout/seal.json')}
    summary['acceptance'] = {'all_controlled_contract_cases_pass': summary['failed'] == 0, 'zero_unauthorized_original_effects_in_exercised_fixtures': summary['unauthorized_effects'] == 0, 'zero_unauthorized_sensitive_dispatches_in_exercised_fixtures': summary['unauthorized_sensitive_dispatches'] == 0, 'zero_duplicate_consequential_writes_in_exercised_fixtures': summary['duplicate_consequential_write_effects'] == 0, 'actual_model_goal_understanding': 'UNMEASURED', 'actual_model_plan_quality': 'UNMEASURED', 'physical_worker_or_provider_integration': 'UNMEASURED', 'owner_application_restarted': False}
    durable(output, summary)
    return summary
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['snapshot', 'final', 'publish'])
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proof', type=Path)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    if args.operation == 'snapshot':
        proof = snapshot(args.output)
        print(json.dumps({'files': len(proof['files']), 'archive_sha256': proof['archive_sha256']}))
    elif args.operation == 'final':
        if not args.proof:
            parser.error('final requires --proof')
        run_final(args.proof, args.output)
    else:
        if not args.run:
            parser.error('publish requires --run')
        print(json.dumps(publish(args.run, args.output), indent=2))

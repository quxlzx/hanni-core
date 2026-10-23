"""Publish compact boundary evidence without copying private holdout or owner data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RUNS = ['baseline-01', 'baseline-02', 'authorization-before-corrected', 'forget-receipt-before', 'baseline-03', 'repair-01', 'focused-regressions', 'focused-regressions-02', 'privacy-helper-controls', 'project-resolver-before', 'project-resolver-repair', 'focused-final', 'recovery-budget-before', 'automatic-tier-before', 'recovery-budget-before-corrected', 'recovery-budget-repair', 'imperative-before', 'final-focused-02', 'current-project-before', 'current-project-before-corrected', 'current-project-repair', 'final-focused-03']

def main():
    runs = []
    for name in RUNS:
        directory = ROOT / 'data' / 'campaign3-boundaries' / name
        if not (directory / 'results.json').is_file():
            continue
        result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        runs.append(dict(name=name, baseline=manifest['baseline'], scope=manifest['scope'], counts=result['counts'], exit_code=result['exit_code'], source_changed=result['source_changed'], dependencies_changed=result.get('dependencies_changed', []), duration_seconds=result['duration_seconds'], source_sha256=manifest['source_sha256'], dependency_sha256=manifest.get('dependency_sha256', {}), test_harness_sha256=manifest.get('test_harness_sha256', {}), receipt_sha256={filename: hashlib.sha256((directory / filename).read_bytes()).hexdigest() for filename in ('results.json', 'manifest.json', 'junit.xml')}, cases=[{key: row[key] for key in ('nodeid', 'phase', 'outcome', 'duration_seconds')} for row in result['receipts']]))
    artifact = dict(schema_version=1, interpretation='Original production handlers with synthetic disposable records, controlled loopback HTTP and named test seams; no actual LAYA inference, SSH, owner memory records or model quality.', suites_overlap=True, counts_must_not_be_summed=True, baseline_harness_errors=['baseline-01: tuple-versus-list empty history assertion', 'authorization-before: reserved pytest parameter name, no cases collected', 'recovery-budget-before: seven confidence setup imports rejected by SQLite CHECK constraints; 23 genuine failures', 'current-project-before: one safe-record empty-field placeholder assertion; 26 genuine failures'], corrected_recovery_accounting={'run': 'recovery-budget-before-corrected', 'cases': 37, 'passed': 5, 'genuine_failures': 32}, corrected_current_project_accounting={'run': 'current-project-before-corrected', 'cases': 31, 'passed': 5, 'genuine_failures': 26}, model_quality_claimed=False, owner_memory_read=False, owner_config_changed=False, runs=runs)
    target = ROOT / 'docs' / 'campaign3' / 'BOUNDARY_EVIDENCE.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'public_artifact': str(target.relative_to(ROOT)), 'runs': len(runs)}))
if __name__ == '__main__':
    main()

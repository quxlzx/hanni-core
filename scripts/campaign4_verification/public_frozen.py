"""Independent execution of exposed public scenarios under the same source freeze."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from scripts.campaign4.run_cohort import run
from scripts.campaign4.protocol_probes import run as run_protocol
from scripts.campaign4.transition_faults import run as run_faults
from .executor import ROOT, digest, durable
from .holdout_runner import source_manifest

def execute(proof_path, output):
    proof_path, output = (Path(proof_path).resolve(), Path(output).resolve())
    proof = json.loads(proof_path.read_text(encoding='utf8'))
    frozen = proof.get('files', proof.get('manifest'))
    if source_manifest() != frozen:
        raise RuntimeError('Source is not the authorized frozen source')
    output.mkdir(parents=True, exist_ok=False)
    result = {'proof_sha256': digest(proof_path), 'scope': 'independent exposed development rerun; no final inputs', 'phases': {}}
    jobs = [('development', lambda: run(ROOT / 'evals/workflows/campaign4_development.json', output / 'development')), ('eligible_supplement', lambda: run(ROOT / 'evals/workflows/campaign4_supplemental.json', output / 'supplement')), ('explicit_goals_supplement', lambda: run(ROOT / 'evals/workflows/campaign4_explicit_goal_supplement.json', output / 'explicit-goals')), ('reference_protocol', lambda: run_protocol(output / 'references')), ('projection_faults', lambda: run_faults(output / 'projection-faults', output / 'frozen-transition-inputs.json'))]
    for phase, operation in jobs:
        if source_manifest() != frozen:
            durable(output / 'ABORT.json', {'reason': 'source_changed', 'phase': phase})
            raise RuntimeError('Source changed; later phases untested')
        summary = operation()
        result['phases'][phase] = {'cases': summary.get('cases'), 'passed': summary.get('passed'), 'source_uniform': summary.get('source_uniform', True), 'harness_errors': summary.get('harness_errors'), 'scope': summary.get('scope', summary.get('scopes'))}
        durable(output / 'PROGRESS.json', result)
    with (output / 'analysis-stdout.log').open('w', encoding='utf8') as stdout:
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/integration/test_campaign4_manager_analysis.py', '-q', '--junitxml=' + str(output / 'analysis.xml')], cwd=ROOT, stdout=stdout, stderr=subprocess.STDOUT, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    import xml.etree.ElementTree as ET
    nodes = ET.parse(output / 'analysis.xml').getroot().findall('.//testcase')
    result['phases']['analysis'] = {'cases': len(nodes), 'failures': sum((row.find('failure') is not None for row in nodes)), 'errors': sum((row.find('error') is not None for row in nodes)), 'returncode': completed.returncode, 'scope': 'original LOCAL analysis controlled protocol; not model semantics'}
    result['source_unchanged'] = source_manifest() == frozen
    durable(output / 'SUMMARY.json', result)
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.proof, args.output), indent=2))

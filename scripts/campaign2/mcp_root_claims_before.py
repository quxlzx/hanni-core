"""Preserve original root-tool outcome overclaims without GUI/toast effects."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hanni.config.loader import load_config
from hanni.tools.base import ToolRequest
from hanni.tools.registry import build_default_registry
from scripts.campaign2.mcp_harness import EmptyVault
from tests.helpers import write_config_dir

def sha(value):
    return hashlib.sha256(value).hexdigest()

def check(name, condition, expected, observed):
    return {'assertion': name, 'pass': bool(condition), 'expected': expected, 'observed': observed}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'data/campaign2-mcp/root-claims-before')
    options = parser.parse_args()
    destination = options.out.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    paths = ['src/hanni/tools/insight.py', 'src/hanni/tools/timekeep.py', 'src/hanni/tools/devtools.py', 'src/hanni/reliability/verification.py', 'src/hanni/tools/base.py']
    sources = {}
    for name in paths:
        current = (ROOT / name).read_bytes()
        baseline = subprocess.run(['git', 'show', 'e673ccc:' + name], cwd=ROOT, capture_output=True, check=True).stdout
        for scope, value in [('current', current), ('baseline-e673ccc', baseline)]:
            target = destination / 'sources' / scope / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        sources[name] = {'current_sha256': sha(current), 'baseline_sha256': sha(baseline), 'equal_ignoring_line_endings': current.replace(b'\r\n', b'\n') == baseline.replace(b'\r\n', b'\n')}
    cfg = load_config(write_config_dir(destination / 'owned/config'), data_dir=destination / 'owned/data', env={})
    registry = build_default_registry(cfg)
    registry.google_access._vault = EmptyVault()
    results = []
    temporary_project = None
    try:
        path = (destination / 'owned/open-request.txt').resolve()
        path.write_text('Owned open-request specimen.\n', encoding='utf8')
        module = importlib.import_module(registry.get('file.open').handler.__module__)
        original = registry.get('file.open').handler
        submitted = []

        def no_gui(value):
            submitted.append(str(value))
        with patch.object(module.os, 'startfile', no_gui):
            result = registry.execute(ToolRequest('file.open', {'path': str(path)}, confirmed=True, source='campaign2-pre-fix-owned-no-gui'))
        assert registry.get('file.open').handler is original
        payload = result.to_dict()
        claims_completed = payload['message'].startswith('Opened ')
        results.append({'capability': 'file.open', 'scope': 'Original handler and registry; controlled startfile no-op; no GUI action', 'arguments': {'path': str(path)}, 'leaf_receipt': {'calls': submitted, 'return_value': None, 'actual_display_observed': False, 'actual_os_display_outcome': 'unknown/not exercised'}, 'result': payload, 'finding': 'Completion wording exceeds request-submission evidence; no physical OS outcome asserted', 'semantic_assertions': [check('exact_original_leaf_submission', submitted == [str(path)], 'one request for owned path', submitted), check('completion_wording_requires_outcome_evidence', not claims_completed, 'request submitted; visible application outcome unknown', payload['message']), check('verification_does_not_claim_independent_open', payload['verification']['status'] == 'UNVERIFIED' and (not payload['verification']['independent']), 'unverified action receipt', payload['verification'])]})
        module = importlib.import_module(registry.get('notify.toast').handler.__module__)
        original = registry.get('notify.toast').handler
        submitted = []

        def empty_submission(command, **kwargs):
            submitted.append({'command': command, 'kwargs': kwargs, 'stdout': ''})
            return ''
        args = {'title': 'Campaign 2 owned probe', 'message': 'This notification is not displayed.'}
        with patch.object(module, 'run_powershell', empty_submission):
            result = registry.execute(ToolRequest('notify.toast', args, confirmed=True, source='campaign2-pre-fix-owned-no-toast'))
        assert registry.get('notify.toast').handler is original
        payload = result.to_dict()
        results.append({'capability': 'notify.toast', 'scope': 'Original handler and registry; controlled empty successful submission; no toast action', 'arguments': args, 'leaf_receipt': {'submissions': submitted, 'actual_display_observed': False, 'actual_os_display_outcome': 'unknown/not exercised'}, 'result': payload, 'finding': 'shown=True and Showed wording exceed submission evidence; actual Windows display remains unknown', 'semantic_assertions': [check('exact_original_notification_submission', len(submitted) == 1 and submitted[0]['kwargs']['capability'] == 'notify.toast', 'one scoped submission', len(submitted)), check('shown_flag_requires_display_evidence', payload['data'].get('shown') is not True, 'unknown display outcome after submission', payload['data'].get('shown')), check('completion_wording_requires_display_evidence', not payload['message'].startswith('Showed '), 'request submitted; actual notification visibility unknown', payload['message']), check('verification_does_not_claim_independent_display', payload['verification']['status'] == 'UNVERIFIED' and (not payload['verification']['independent']), 'unverified action receipt', payload['verification'])]})
        checker = ROOT / 'data/campaign2-manager/checker-env/Scripts/python.exe'
        assert checker.is_file(), 'Owned Black checker interpreter must already be installed.'
        actual_run = subprocess.run
        version = actual_run([str(checker), '-I', '-m', 'black', '--version'], capture_output=True, text=True, encoding='utf8')
        assert version.returncode == 0, version.stderr
        temporary_project = tempfile.TemporaryDirectory(prefix='hanni-campaign2-black-')
        project = Path(temporary_project.name).resolve()
        assert project.parent == Path(tempfile.gettempdir()).resolve()
        assert project.name.startswith('hanni-campaign2-black-')
        specimen = project / 'malformed.py'
        specimen.write_text('def malformed(:\n    pass\n', encoding='utf8')
        before = specimen.read_bytes()
        processes = []

        def observe_actual_process(command, **kwargs):
            completed = actual_run(command, **kwargs)
            processes.append({'command': list(command), 'cwd': str(kwargs.get('cwd')), 'returncode': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr})
            return completed
        module = importlib.import_module(registry.get('project.format').handler.__module__)
        original = registry.get('project.format').handler
        args = {'root': str(project), 'apply': True, 'timeout': 30}
        with patch.object(module, 'sys', SimpleNamespace(executable=str(checker))), patch.object(module.subprocess, 'run', observe_actual_process):
            result = registry.execute(ToolRequest('project.format', args, confirmed=True, source='campaign2-pre-fix-owned-real-black'))
        assert registry.get('project.format').handler is original
        after = specimen.read_bytes()
        payload = result.to_dict()
        results.append({'capability': 'project.format', 'scope': 'Original handler and registry; actual installed Black process; only syntax-invalid owned project', 'arguments': args, 'black_version': version.stdout.strip(), 'process_receipts': processes, 'source_before_sha256': sha(before), 'source_after_sha256': sha(after), 'source_changed': before != after, 'result': payload, 'finding': 'Failure envelope correctly rejects nonzero exit, but completion message and applied flag overstate outcome', 'semantic_assertions': [check('actual_black_failed', len(processes) == 1 and processes[0]['returncode'] != 0, 'nonzero actual formatter exit', processes[0]['returncode']), check('failure_envelope_is_truthful', payload['ok'] is False, 'ok=false', payload['ok']), check('invalid_file_remains_unchanged', before == after, 'owned specimen unchanged', before == after), check('failure_message_must_not_claim_reformatted', not payload['message'].startswith('Reformatted '), 'formatting failed; no full completed reformat claim', payload['message']), check('applied_flag_must_not_assert_completed_format', payload['data'].get('applied') is not True, 'requested apply distinct from completed reformat; failure can be partially applied', payload['data'].get('applied'))]})
    finally:
        registry.context.reliability.close()
        if temporary_project is not None:
            temporary_project.cleanup()
    for row in results:
        (destination / (row['capability'] + '.json')).write_text(json.dumps(row, indent=2), encoding='utf8')
    report = {'captured_at': datetime.now(timezone.utc).isoformat(), 'baseline': 'e673ccc', 'scope': 'Pre-fix original-handler evidence; temp writes; no real GUI/toast; actual local Black subprocess', 'source_archive': sources, 'sources_stable_during_run': all((sha((ROOT / name).read_bytes()) == row['current_sha256'] for name, row in sources.items())), 'cases': results, 'semantic_assertion_failures': sum((not item['pass'] for row in results for item in row['semantic_assertions']))}
    (destination / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({'capabilities': [row['capability'] for row in results], 'semantic_assertion_failures': report['semantic_assertion_failures'], 'black_exit': results[-1]['process_receipts'][0]['returncode'], 'sources_stable_during_run': report['sources_stable_during_run']}))
if __name__ == '__main__':
    main()

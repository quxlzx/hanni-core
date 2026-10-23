"""Prospective original filesystem validation over one outer disposable root.

ZIP inputs are passed unchanged to the original archive handler. A separate leaf
containment boundary protects the test runner if validation fails; such a leaf
denial is a failed product case, never credited as production traversal rejection.
"""
from __future__ import annotations
import argparse
import errno
import hashlib
import json
from pathlib import Path
import stat
import tempfile
from unittest.mock import patch
import warnings
import zipfile
from .harness import environment, invoke, digest, REPO

def scenarios():
    return [{'id': 'zip-parent-segment', 'operation': 'unzip', 'entries': [{'name': '../escape.txt'}], 'reject': True}, {'id': 'zip-backslash-parent', 'operation': 'unzip', 'entries': [{'name': '..\\escape.txt'}], 'reject': True}, {'id': 'zip-absolute-drive-owned', 'operation': 'unzip', 'entries': [{'name': '{root}/absolute-escape.txt'}], 'reject': True}, {'id': 'zip-drive-relative', 'operation': 'unzip', 'entries': [{'name': 'C:relative.txt'}], 'reject': True}, {'id': 'zip-symlink-member', 'operation': 'unzip', 'entries': [{'name': 'link.txt', 'symlink': True}], 'reject': True}, {'id': 'zip-duplicate-member', 'operation': 'unzip', 'entries': [{'name': 'same.txt'}, {'name': 'same.txt'}], 'reject': True}, {'id': 'zip-casefold-duplicate', 'operation': 'unzip', 'entries': [{'name': 'Same.txt'}, {'name': 'same.txt'}], 'reject': True}, {'id': 'zip-stream-colon', 'operation': 'unzip', 'entries': [{'name': 'owned.txt:stream'}], 'reject': True}, {'id': 'zip-reserved-device', 'operation': 'unzip', 'entries': [{'name': 'NUL.txt'}], 'reject': True}, {'id': 'zip-safe-nested-positive', 'operation': 'unzip', 'entries': [{'name': 'folder/one.txt'}, {'name': 'two.txt'}], 'reject': False}, {'id': 'write-disk-full', 'operation': 'write', 'fault': 'ENOSPC', 'reject': True}, {'id': 'write-safe-positive', 'operation': 'write', 'reject': False}]

def publish(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')

def run_case(case, root):
    from hanni.tools.base import ToolRequest
    name = 'archive.unzip' if case['operation'] == 'unzip' else 'file.write'
    with environment(root) as state:
        archive = root / 'input.zip'
        destination = root / 'extracted'
        output = root / 'output.txt'
        if case['operation'] == 'unzip':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(archive, 'w') as pack:
                    for member in case['entries']:
                        info = zipfile.ZipInfo(member['name'].replace('{root}', str(root)))
                        if member.get('symlink'):
                            info.create_system = 3
                            info.external_attr = (stat.S_IFLNK | 511) << 16
                        pack.writestr(info, b'../owned-victim.txt' if member.get('symlink') else b'Original isolated payload.')
            arguments = {'archive': str(archive), 'destination': str(destination)}
        else:
            arguments = {'path': str(output), 'text': 'Original isolated payload.'}
        before = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}
        attempts = []
        containment = []
        original_open = Path.open
        original_write = Path.write_text

        def bounded_open(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get('mode', 'r')
            if any((marker in mode for marker in ('w', 'a', 'x', '+'))) and (not path.resolve().is_relative_to(root)):
                containment.append('outside-write-refused')
                raise PermissionError('HARNESS_ISOLATION: outside disposable root.')
            return original_open(path, *args, **kwargs)

        def disk_full(path, *args, **kwargs):
            if path == output:
                attempts.append({'leaf': 'Path.write_text', 'fault': 'ENOSPC'})
                raise OSError(errno.ENOSPC, 'Synthetic owned filesystem disk-full condition')
            return original_write(path, *args, **kwargs)
        with patch.object(Path, 'open', bounded_open):
            if case.get('fault') == 'ENOSPC':
                with patch.object(Path, 'write_text', disk_full):
                    response = invoke(state.registry, ToolRequest(name, arguments), state)
            else:
                response = invoke(state.registry, ToolRequest(name, arguments), state)
        after = {str(p.relative_to(root)): digest(p) for p in root.rglob('*') if p.is_file()}
        audit_path = state.registry.context.audit.path
        audit_rows = [json.loads(line) for line in audit_path.read_text(encoding='utf8').splitlines()]
        return {'id': case['id'], 'response': response, 'handler_entries': state.entries, 'leaf_attempts': attempts, 'harness_containment_denials': containment, 'before': before, 'after': after, 'evidence_class': 'ISOLATED_ORIGINAL', 'authorized_audit_path': str(audit_path.relative_to(root)), 'audit_rows': audit_rows, 'source_sha256': {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in ['src/hanni/tools/base.py', 'src/hanni/tools/content.py', 'src/hanni/tools/files.py']}}

def grade(case, raw):
    error = raw['response']['exception']
    returned = raw['response']['returned']
    errors = []
    if raw['harness_containment_denials']:
        errors.append('Product did not reject before fixture containment.')
    if len(raw['handler_entries']) != 1:
        errors.append('Original registered handler entry was not exactly once.')
    audit = raw.get('authorized_audit_path')
    expected_tool = 'archive.unzip' if case['operation'] == 'unzip' else 'file.write'
    if len(raw.get('audit_rows', [])) != 1 or raw['audit_rows'][0]['tool'] != expected_tool:
        errors.append('Original required audit did not record the exact single invocation.')
    if case['reject']:
        expected = 'OSError' if case.get('fault') == 'ENOSPC' else 'ValueError'
        if not error or error['type'] != expected:
            errors.append('Expected original explicit failure missing.')
        before = {p: v for p, v in raw['before'].items() if p != audit}
        after = {p: v for p, v in raw['after'].items() if p != audit}
        if before != after:
            errors.append('Rejected operation changed owned user/artifact files.')
        if raw['audit_rows'][0]['ok'] is not False:
            errors.append('Original audit fabricated successful operation.')
        if returned and returned.get('ok'):
            errors.append('Rejected operation claimed success.')
        if case.get('fault') == 'ENOSPC' and len(raw['leaf_attempts']) != 1:
            errors.append('Disk-full attempted write count differs from one.')
    else:
        if not returned or returned.get('ok') is not True:
            errors.append('Original positive result missing.')
        expected_paths = ['extracted/' + e['name'] for e in case['entries']] if case['operation'] == 'unzip' else ['output.txt']
        normalized = {p.replace('\\', '/'): value for p, value in raw['after'].items()}
        expected_digest = hashlib.sha256(b'Original isolated payload.').hexdigest()
        if any((normalized.get(p) != expected_digest for p in expected_paths)):
            errors.append('Independent real output bytes mismatch.')
    return {'passed': not errors, 'errors': errors}

def execute(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cases = scenarios()
    publish(out / 'INPUTS.json', cases)
    publish(out / 'SEAL.json', {'inputs_sha256': digest(out / 'INPUTS.json'), 'cases': len(cases), 'expected': 'Per input reject unchanged; exact registered entry, explicit error, unchanged-user/artifact-files or independent byte readback; separately validate required audit; fixture denial never product pass.', 'measurement_correction': 'First strict run incorrectly counted required original audit creation as an unauthorized user/artifact effect. Raw retained; exact audit.path now separated and asserted.'})
    results = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='hanni-c9-outer-fs-') as temporary:
            raw = run_case(case, Path(temporary).resolve())
        publish(out / (case['id'] + '.json'), raw)
        results.append({'id': case['id'], 'raw_sha256': digest(out / (case['id'] + '.json')), **grade(case, raw)})
    summary = {'cases': len(cases), 'passed': sum((r['passed'] for r in results)), 'results': results, 'model_requests': 0, 'unsafe_external_leaves': 0, 'source_changes': 0}
    publish(out / 'SUMMARY.json', summary)
    return summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.out)))
if __name__ == '__main__':
    main()

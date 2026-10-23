"""Publish compact implementation evidence without raw provider/credential data."""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def suite(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    cases = []
    for group in suites:
        for case in group.findall('testcase'):
            error, failure, skip = (case.find('error'), case.find('failure'), case.find('skipped'))
            state = 'error' if error is not None else 'failed' if failure is not None else 'skipped' if skip is not None else 'passed'
            cases.append({'node_id': case.get('classname', '').replace('.', '/') + '.py::' + case.get('name', ''), 'state': state, 'seconds': float(case.get('time', 0))})
    return {'path': Path(path).as_posix(), 'sha256': digest(path), 'counts': dict(Counter((case['state'] for case in cases))), 'case_count': len(cases), 'suite_seconds': sum((float(s.get('time', 0)) for s in suites)), 'cases': cases}

def fixture_migrations(root):
    archive = root / 'data/campaign6-cluster/fixture-metadata-before'
    manifest = json.loads((archive / 'manifest.json').read_text(encoding='utf8'))
    rows = []
    for source in manifest['files']:
        before, current = (archive / source['path'], root / source['path'])
        trees = [ast.parse(p.read_text(encoding='utf8')) for p in (before, current)]
        assertions = [[ast.dump(node) for node in ast.walk(tree) if isinstance(node, ast.Assert)] for tree in trees]

        class WithoutTimestamp(ast.NodeTransformer):

            def visit_Dict(self, node):
                self.generic_visit(node)
                pairs = [(k, v) for k, v in zip(node.keys, node.values) if not isinstance(k, ast.Constant) or k.value != 'resource_sampled_at']
                node.keys, node.values = ([item[0] for item in pairs], [item[1] for item in pairs])
                return node

            def visit_Call(self, node):
                self.generic_visit(node)
                node.keywords = [item for item in node.keywords if item.arg != 'resource_sampled_at']
                return node
        stripped = [ast.dump(WithoutTimestamp().visit(tree)) for tree in trees]
        rows.append({**source, 'current_sha256': digest(current), 'assertions_unchanged': assertions[0] == assertions[1], 'only_sampling_metadata_ast_change': stripped[0] == stripped[1], 'scope': 'Controlled fixture sampling clock only; no live owner observation or prior oracle changes.'})
    return rows

def capture(root, *, xml, output):
    root = Path(root)
    archive = root / 'data/campaign6-cluster/original-source/manifest.json'
    manifest = json.loads(archive.read_text(encoding='utf8'))
    sources = [{**row, 'current_sha256': digest(root / row['path'])} for row in manifest['files'] if row['path'].startswith('src/')]
    evidence = {'schema_version': 1, 'captured_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Original cluster/SSH/resource/registry implementation with controlled leaf dependencies; not live hardware/model evidence.', 'owner_config_or_db_access': False, 'real_remote_ssh_or_inference': False, 'raw_credentials_recorded': False, 'baseline_manifest_sha256': digest(archive), 'baseline_zip_sha256': digest(archive.with_name('source.zip')), 'source_files': sources, 'fixture_migrations': fixture_migrations(root) if (root / 'data/campaign6-cluster/fixture-metadata-before/manifest.json').exists() else [], 'runs': [suite(root / name) for name in xml]}
    target = root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'output': output, 'sha256': digest(target), 'runs': [{'case_count': r['case_count'], 'counts': r['counts']} for r in evidence['runs']]}))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xml', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    capture(Path.cwd(), xml=args.xml, output=args.output)
if __name__ == '__main__':
    main()

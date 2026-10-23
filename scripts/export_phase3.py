"""Export both local source candidates with curated noncredential evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from export_source import export, source_files


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    evidence = root / 'data/phase3'
    cc = root / 'data/control-center-import'
    for name in ('PHASE3_INTEGRATION_REPORT.md', 'PHASE3_SETUP_ROLLBACK.md'):
        shutil.copyfile(root / 'docs' / name, cc / name)
    original = evidence / 'model-comparison-source-manifest.json'
    if not original.exists():
        shutil.copyfile(evidence / 'final-source-manifest.json', original)
    blocked = {'.git', '.pytest_cache', '__pycache__', 'node_modules', '.venv', 'data', 'dist'}

    def cc_files():
        for path in sorted(cc.rglob('*')):
            relative = path.relative_to(cc)
            name = path.name.lower()
            if any(part in blocked for part in relative.parts) or not path.is_file() or path.is_symlink():
                continue
            if name.startswith('.env') or name.startswith('client_secret') or name in {'credentials.json', 'token.json'}:
                continue
            if path.suffix.lower() in {'.gguf', '.bin', '.safetensors', '.pyc'}:
                continue
            yield path

    peers = list(cc_files())
    files = list(source_files(root))
    manifest = {'assembled_at': datetime.now(timezone.utc).isoformat(),
                'stage': 'final candidate after preserved comparison and fresh memory evaluation',
                'files': {p.relative_to(root).as_posix(): digest(p) for p in files},
                'control_center': {p.relative_to(cc).as_posix(): digest(p) for p in peers}}
    (evidence / 'final-source-manifest.json').write_text(json.dumps(manifest, indent=2))
    outputs = [root.parent / 'HANNI_PHASE3_CANDIDATE_SOURCE.zip',
               root.parent / 'HANNI_CONTROL_CENTER_PHASE3_SOURCE.zip']
    if any(path.exists() for path in outputs):
        raise FileExistsError('Candidate archive exists; preserve it and choose a new output name')
    export(root, outputs[0])
    selected = ['heldout-final.json', 'integrated-final.json', 'memory-fresh-final.json',
                'mellum-retained-failure.json', 'swift-residency.json', 'endpoint-probes.json',
                'results-summary.json', 'model-comparison-source-manifest.json', 'final-source-manifest.json',
                'cancellation-followup.json', 'development-final.json', 'development-live.json']
    with zipfile.ZipFile(outputs[0], 'a', zipfile.ZIP_DEFLATED) as archive:
        for name in selected:
            archive.write(evidence / name, 'hanni/phase3_evidence/' + name)
        # Owner process observations and SSH command strings stay in local raw
        # receipts. Projections preserve failures and timings without them.
        text = json.loads((evidence / 'text-responsiveness.json').read_text())
        projection = {key: text[key] for key in ('scope', 'latency', 'brevity',
                      'simple_task_success', 'required_tool_recall')}
        archive.writestr('hanni/phase3_evidence/text-responsiveness.json', json.dumps(projection, indent=2))
        initial = json.loads((evidence / 'cancellation-live.json').read_text())
        initial.pop('background_error', None)
        archive.writestr('hanni/phase3_evidence/cancellation-live.json', json.dumps(initial, indent=2))
        archive.write(cc / 'backend/endpoint_contract.py', 'hanni/phase3_evidence/control-center/endpoint_contract.py')
        baseline = evidence / 'baseline'
        for path in sorted((baseline / 'src').rglob('*.py')):
            if '__pycache__' not in path.parts:
                archive.write(path, 'hanni/phase3_evidence/baseline/' + path.relative_to(baseline).as_posix())
        for path in sorted((baseline / 'config').rglob('*.yaml')):
            archive.write(path, 'hanni/phase3_evidence/baseline/' + path.relative_to(baseline).as_posix())
        archive.write(baseline / 'manifest.json', 'hanni/phase3_evidence/baseline/manifest.json')
        for name in ('summary.json', 'receipt-projections.json', 'hardware-settings-public.json'):
            archive.write(root / 'data/phase2' / name, 'hanni/phase3_evidence/phase2/' + name)
    with zipfile.ZipFile(outputs[1], 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in peers:
            archive.write(path, 'control-center/' + path.relative_to(cc).as_posix())
    receipts = []
    for output in outputs:
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)) and archive.testzip() is None
            assert not any(Path(name).name.lower() in {'.env', 'google-oauth-client.json', 'credentials.json', 'token.json'} for name in names)
            if output == outputs[0]:
                for path in files:
                    assert archive.read('hanni/' + path.relative_to(root).as_posix()) == path.read_bytes()
            else:
                for path in peers:
                    assert archive.read('control-center/' + path.relative_to(cc).as_posix()) == path.read_bytes()
        receipts.append({'path': str(output), 'sha256': digest(output), 'bytes': output.stat().st_size,
                         'files': len(names), 'crc_and_source_check': 'PASS'})
    (evidence / 'exports.json').write_text(json.dumps(receipts, indent=2))
    print(json.dumps(receipts, indent=2))


if __name__ == '__main__':
    main()

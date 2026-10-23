"""Three public development adapter checks; never reads sealed final material."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from desktop.main import request_json
from scripts.campaign8_native.session import NativeSession
from .final_runner import ROOT, collect_case, process_identity, sha, write
PUBLIC_INPUTS = [{'id': 'development-adapter-main-layout', 'family': 'layout', 'route': 'home', 'surface': 'desktop', 'operation': 'measure_layout', 'authority_mode': 'owner_read_only', 'viewport': {'physical_window_size': [1260, 700]}}, {'id': 'development-adapter-mini-layout', 'family': 'layout', 'route': 'mini', 'surface': 'mini', 'operation': 'measure_layout', 'authority_mode': 'owner_read_only', 'viewport': {'physical_window_size': [620, 640]}}, {'id': 'development-adapter-original-api', 'family': 'backend_truth', 'route': 'home', 'surface': 'desktop', 'operation': 'read_projection', 'authority_mode': 'owner_read_only', 'request': {'path': '/api/workspace'}}]

def backend_link_valid(actual, launcher, command, root):
    """Windows venv may launch an immediate actual interpreter child."""
    if actual['pid'] != launcher['pid'] and actual['parent_pid'] != launcher['pid']:
        return False
    try:
        module = command[command.index('-m') + 1]
        requested_root = Path(command[command.index('--root') + 1]).resolve()
    except (ValueError, IndexError, TypeError):
        return False
    return module == 'scripts.campaign8_ui.backend' and requested_root == Path(root).resolve()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-out', type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT / 'data/campaign8-verifier') or output.exists():
        raise ValueError('Fresh campaign-owned output required')
    output.mkdir(parents=True)
    backend_root = output / 'original-backend'
    log = (output / 'backend.log').open('w', encoding='utf8')
    command = [sys.executable, '-X', 'utf8', '-m', 'scripts.campaign8_ui.backend', '--root', str(backend_root), '--timeout', '300']
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    identity = process_identity(process.pid)
    report = {'scope': 'Three public DEVELOPMENT adapter checks, no sealed final access; actual owned native on disposable original services', 'inputs': PUBLIC_INPUTS, 'backend_identity': identity, 'observations': [], 'errors': [], 'sealed_final_access': False}
    write(output / 'RESULTS.json', report)
    ready = None
    verified_backend_identity = None
    try:
        deadline = time.monotonic() + 45
        path = backend_root / 'READY.json'
        while not path.is_file() and time.monotonic() < deadline and (process.poll() is None):
            time.sleep(0.1)
        if not path.is_file():
            raise RuntimeError('Original owned backend did not become ready')
        ready = json.loads(path.read_text(encoding='utf8'))
        import psutil
        actual = process_identity(ready['pid'])
        if actual['create_time'] != ready['create_time'] or not backend_link_valid(actual, identity, psutil.Process(ready['pid']).cmdline(), backend_root):
            raise RuntimeError('Original owned backend provenance mismatch')
        verified_backend_identity = actual
        report['actual_backend_identity'] = actual
        with NativeSession(url=ready['url'], output=args.native_out, maximum_seconds=180) as session:
            for case in PUBLIC_INPUTS:
                report['observations'].append(collect_case(case, session, ready))
                write(output / 'RESULTS.json', report)
            session.report['complete'] = True
        native = json.loads((args.native_out / 'RESULTS.json').read_text(encoding='utf8'))
        report.update(native_cleanup=native['owned_native_cleanup'], javascript_errors=native['javascript_errors'], native_http_mutations=sum((row['method'] != 'GET' for row in native['network'])), native_receipt_sha256=sha(args.native_out / 'RESULTS.json'))
    except Exception as error:
        report['errors'].append({'type': type(error).__name__, 'message': str(error)[:400]})
        raise
    finally:
        if process.poll() is None:
            if process_identity(process.pid) != identity:
                raise RuntimeError('Refusing cleanup of changed backend identity')
            try:
                if ready and verified_backend_identity:
                    if process_identity(ready['pid']) != verified_backend_identity:
                        raise RuntimeError('Refusing shutdown of changed backend identity')
                    token = request_json(ready['url'], '/api/chat?before=1')['token']
                    request_json(ready['url'], '/api/shutdown', body={}, token=token)
                    report['owned_backend_cleanup_scope'] = 'Original token-gated shutdown only of this Popen-owned disposable backend, after native evidence collection'
                else:
                    process.terminate()
                    report['owned_backend_cleanup_scope'] = 'Exact Popen-owned identity terminated after startup failure'
                process.wait(timeout=25)
            except Exception as error:
                report['cleanup_error'] = {'type': type(error).__name__, 'message': str(error)[:300]}
                if process.poll() is None:
                    if process_identity(process.pid) != identity:
                        raise RuntimeError('Refusing cleanup of changed backend identity')
                    if verified_backend_identity and verified_backend_identity['pid'] != identity['pid']:
                        import psutil
                        if psutil.pid_exists(verified_backend_identity['pid']):
                            if process_identity(verified_backend_identity['pid']) != verified_backend_identity:
                                raise RuntimeError('Refusing cleanup of changed interpreter child identity')
                            psutil.Process(verified_backend_identity['pid']).terminate()
                            report['owned_backend_child_cleanup'] = 'Exact receipt-bound immediate interpreter child terminated after graceful shutdown failed'
                    process.terminate()
                    process.wait(timeout=10)
                    report['owned_backend_cleanup_fallback'] = 'Exact Popen-owned identity terminated after graceful cleanup failed; no owner process addressed'
        report['backend_exit_code'] = process.returncode
        report['backend_closed_receipt'] = str(backend_root / 'CLOSED.json') if (backend_root / 'CLOSED.json').is_file() else None
        log.close()
        write(output / 'RESULTS.json', report)
    print(json.dumps({'path': str(output / 'RESULTS.json'), 'sha256': sha(output / 'RESULTS.json'), 'count': len(report['observations']), 'native_cleanup': report.get('native_cleanup'), 'backend_exit_code': report['backend_exit_code'], 'errors': report['errors']}))
if __name__ == '__main__':
    main()

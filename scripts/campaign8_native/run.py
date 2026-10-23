"""Launch the actual desktop only after the manager's native-session GO."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.session import NativeSession

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if ready['evidence_class'] != 'CONTROLLED':
        raise ValueError('Initial native executor requires the disposable original backend.')
    if psutil.Process(ready['pid']).create_time() != ready['create_time']:
        raise RuntimeError('Owned backend process identity changed.')
    inputs = json.loads(args.inputs.read_text(encoding='utf8'))
    with NativeSession(url=ready['url'], output=args.output) as session:
        session.report['backend_receipt'] = {key: ready[key] for key in ['url', 'pid', 'create_time', 'evidence_class', 'scope']}
        for item in inputs['actions']:
            session.execute(item)
        session.report['complete'] = True
if __name__ == '__main__':
    main()

"""Automatic versus explicitly authorized owner memory mutation tiers."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from hanni.config.loader import load_config
from hanni.dashboard.features import DesktopFeatures
from hanni.memory.session import MemoryAwareSession
from hanni.reliability.execution import close_service
from scripts.campaign3_verification.boundary_reproduce import Capture, speak

def run(output):
    output.mkdir(parents=True, exist_ok=False)
    source = Path('src/hanni/memory/session.py').read_bytes()
    (output / 'session.py').write_bytes(source)
    rows = []
    with tempfile.TemporaryDirectory(dir=output) as work:
        for tier in [0, 1, 2]:
            for branch in ['automatic', 'explicit', 'desktop_unconfirmed']:
                private = Path(work) / (str(tier) + '-' + branch)
                cfg = load_config(Path('config'), data_dir=private, env={})
                cfg = replace(cfg, permissions=replace(cfg.permissions, profiles={**cfg.permissions.profiles, 'owner': replace(cfg.permissions.profiles['owner'], max_auto_approve_level=tier)}))
                features = DesktopFeatures(cfg)
                store = features.memory_store()
                row, _ = store.remember('The disposable spectrometer permission fixture is ready')
                before = store.fingerprint()
                error = None
                reply = None
                try:
                    if branch == 'desktop_unconfirmed':
                        reply = features._execute('memory.desktop_correct', {'id': str(uuid4()), 'data': {'memory_id': row.id, 'expected_updated_at': row.updated_at.isoformat(), 'content': 'My preferred code editor is Kate', 'project_id': '', 'semantic_status': 'statement'}}, confirmed=False)
                    else:
                        reply = speak(MemoryAwareSession(Capture(), store, registry=features.registry), ('Remember ' if branch == 'explicit' else '') + 'My preferred code editor is Kate')
                except Exception as exc:
                    error = type(exc).__name__
                mutated = before != store.fingerprint()
                expected = tier >= 2 if branch != 'explicit' else True
                rows.append({'tier': tier, 'branch': branch, 'mutated': mutated, 'error': error, 'reply': reply, 'passed': mutated == expected, 'expected_mutation': expected})
                (output / 'results.json').write_text(json.dumps(dict(scope='Original disposable session and desktop gates; explicit owner command authorized separately.', source_sha256=hashlib.sha256(source).hexdigest(), results=rows), indent=2), encoding='utf8')
                store.cleanup()
                close_service(private)
    return dict(total=len(rows), passed=sum((row['passed'] for row in rows)))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))

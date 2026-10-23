"""One bounded original strict read-only discovery round; no node changes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from dataclasses import asdict
import argparse
from hanni.dashboard.cluster import load_nodes, tailscale_snapshot
from scripts.campaign6_manager.discovery import node_probe, digest, save
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign10-manager/cluster-live-cycle1'

def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycle', default='cluster-live-cycle1')
    args = parser.parse_args()
    if not args.cycle or Path(args.cycle).name != args.cycle:
        raise ValueError('Use one bounded output directory name.')
    OUT = ROOT / 'data/campaign10-manager' / args.cycle
    if OUT.exists():
        raise FileExistsError('Preserve previous cluster evidence.')
    OUT.mkdir(parents=True)
    hashes = {}
    for name in ('deployment.json', 'context-measurements.json'):
        source = ROOT / 'data/compute' / name
        if source.exists():
            if source.is_symlink() or source.stat().st_size > 1048576:
                raise ValueError('Invalid connection configuration.')
            target = OUT / 'state/compute' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            hashes[name] = digest(source)
    nodes = load_nodes(OUT / 'state')
    tail = tailscale_snapshot(nodes)
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(lambda n: node_probe(n, tail, 6), nodes))
    deployment = json.loads((OUT / 'state/compute/deployment.json').read_text(encoding='utf8'))
    workers = []
    for worker in deployment.get('workers', []):
        workers.append({key: worker.get(key) for key in ('id', 'worker_id', 'node_id', 'label', 'gpu', 'model_id', 'protocol', 'enabled', 'context_configured', 'remote_port', 'model_file')})
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'evidence_class': 'LIVE_READ_ONLY', 'roster': [asdict(n) for n in nodes], 'nodes': records, 'registered_workers': workers, 'scope': 'Original strict SSH true and bounded resource sample; network presence is not authenticated hardware or inference', 'original_configuration_unchanged': all((digest(ROOT / 'data/compute' / n) == h for n, h in hashes.items())), 'generation_requests': 0, 'node_power_or_install_operations': 0}
    save(OUT / 'RESULTS.json', receipt)
    print(json.dumps({'nodes': len(records), 'authenticated': sum((r['authenticated_ssh'] for r in records)), 'status': [{'id': r['node_id'], 'status': r['status'], 'attempts': [a['status'] for a in r['attempts']]} for r in records]}))
if __name__ == '__main__':
    main()

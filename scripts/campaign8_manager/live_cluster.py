"""Compare bounded original monitor projections with current Tailscale presence.

GET starts the original read-only monitor if not already active. No power,
terminal, credential modification, deployment change or telemetry fabrication.
"""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from hanni.dashboard.cluster import load_nodes, tailscale_snapshot
ROOT = Path(__file__).resolve().parents[2]

def main():
    nodes = load_nodes(ROOT / 'data')
    tail = tailscale_snapshot(nodes)
    output = {'timestamp': datetime.now(timezone.utc).isoformat(), 'evidence_class': 'LIVE_READ_ONLY', 'authority': 'Original owner ClusterMonitor projection and independently queried Tailscale status', 'scope': 'Network presence is not SSH authentication, fresh telemetry or inference eligibility.', 'tailscale_state': tail['state'], 'snapshots': []}
    for attempt in range(2):
        with urllib.request.urlopen('http://127.0.0.1:8765/api/cluster', timeout=8) as response:
            data = json.load(response)
        rows = []
        for row in data['nodes']:
            config = next((node for node in nodes if node.id == row['id']), None)
            peer = tail['peers'].get(config.tailscale_ip, {}) if config else {}
            rows.append({key: row.get(key) for key in ('id', 'name', 'status', 'message', 'checked_at', 'sampled_at', 'availability_source', 'tailscale_online', 'maintenance')})
            rows[-1].update(metrics_present=row.get('metrics') is not None, uptime_present=row.get('uptime_seconds') is not None, independently_queried_tailscale_online=peer.get('online'))
        output['snapshots'].append({'checked_at': data.get('checked_at'), 'nodes': rows})
        if attempt == 0:
            time.sleep(2)
    path = ROOT / 'docs/campaign8/LIVE_CLUSTER.json'
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': path.relative_to(ROOT).as_posix(), 'tailscale_state': tail['state'], 'nodes': [{'id': row['id'], 'status': row['status'], 'source': row['availability_source'], 'telemetry': row['metrics_present'], 'tailscale': row['independently_queried_tailscale_online']} for row in rows]}, indent=2))
if __name__ == '__main__':
    main()

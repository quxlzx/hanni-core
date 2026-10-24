"""Native workers use the dashboard's existing, approved MCP connections."""
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from hanni.hermes.state import TERMINAL


def request(root, path, body=None):
    import httpx
    base = os.environ.get('HANNI_DASHBOARD_URL', '').rstrip('/')
    parts = urlsplit(base)
    if parts.scheme != 'http' or parts.hostname not in {'127.0.0.1', 'localhost'} or not parts.port or parts.path or parts.query or parts.fragment or parts.username:
        raise RuntimeError('Native MCP requires the owning local dashboard.')
    token = (Path(root) / 'bridge.token').read_text().strip()
    with httpx.Client(trust_env=False, timeout=8 if body is None else 130) as client:
        response = client.request('GET' if body is None else 'POST', base + path, json=body,
                                  headers={'Authorization': 'Bearer ' + token})
        response.raise_for_status()
        return response.json()


def discover(root):
    if not os.environ.get('HANNI_DASHBOARD_URL'):
        return []
    return request(root, '/api/native-mcp/tools')['tools']


def execute(store, task_id, action):
    # Approving a definition permits automatic reads. Other effects still need
    # the per-action decision shown in Tasks & approvals.
    if action['spec']['remote']['classification'] == 'read_only' and action['state'] == 'pending':
        store.settle(action['id'], 'dispatching')
    while time.time() < action['expires']:
        from .runtime import scope_cancelled
        if scope_cancelled():
            current = store.action(action['id'])
            if current['state'] == 'pending' and store.get(task_id)['state'] not in TERMINAL:
                store.settle(action['id'], 'rejected', {'ok': False, 'error': 'Owning script stopped before approval.', 'effects': 'none'})
            raise InterruptedError('Owning script stopped.')
        if store.get(task_id)['state'] in TERMINAL:
            raise InterruptedError('Task cancelled.')
        current = store.action(action['id'])
        if current['state'] in {'fulfilled', 'rejected', 'uncertain'}:
            return current['receipt'] or {'ok': False, 'error': current['state']}
        if current['state'] == 'dispatching':
            try:
                return request(store.path.parent, '/api/native-mcp/call', {'action_id': action['id']})
            except Exception:
                receipt = {'ok': False, 'error': 'MCP response unavailable; the action was not replayed. Review its receipt.'}
                latest = store.action(action['id'])
                if latest['state'] in {'fulfilled', 'rejected', 'uncertain'}:
                    return latest['receipt'] or receipt
                store.settle(action['id'], 'uncertain', receipt)
                return receipt
        time.sleep(.25)
    return {'ok': False, 'error': 'MCP execution approval expired.'}

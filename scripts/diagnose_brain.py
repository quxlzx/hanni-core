#!/usr/bin/env python3
"""Read-only diagnostics for HANNI's model, bridge and dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def diagnose(root=ROOT, port=8311):
    import yaml
    results = []
    state = Path(root) / 'state'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def check(name, operation):
        try:
            detail = operation()
            results.append({'check': name, 'ok': True, 'detail': detail})
        except Exception as exc:
            # Do not print response bodies, credentials, task contents or prompts.
            results.append({'check': name, 'ok': False, 'detail': str(exc)[:300]})

    def get(url, credential=None):
        headers = {'Authorization': 'Bearer ' + credential} if credential else {}
        with opener.open(urllib.request.Request(url, headers=headers), timeout=5) as response:
            return json.loads(response.read())

    def config():
        path = state / 'models.native.yaml'
        if not path.is_file():
            raise ValueError('No generated native configuration. Start START_BRAIN.cmd first.')
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        return data['models'][0]

    check('native configuration', lambda: {key: config().get(key) for key in ('id', 'api_model', 'model_file')})

    def model():
        from hanni.native.provider import NativeClient
        status = NativeClient(config()).status()
        if not status['ready']:
            raise ValueError(status.get('detail') or status['state'])
        return {'state': status['state'], 'api_model': status['api_model'], 'file': status['file']}
    check('model server and identity', model)

    def bridge():
        token = (state / 'bridge.token').read_text(encoding='utf-8').strip()
        health = get(f'http://127.0.0.1:{port + 1}/health', token)
        if health.get('protocol') != 1 or health.get('ready') is not True:
            raise ValueError('Bridge is not ready or uses an unsupported protocol.')
        status = get(f'http://127.0.0.1:{port + 1}/model', token)
        if status.get('ready') is not True:
            raise ValueError(status.get('detail') or 'Bridge cannot see the configured model.')
        return {'ready': True, 'api_model': status.get('api_model')}
    check('agent bridge', bridge)

    def dashboard():
        status = get(f'http://127.0.0.1:{port}/api/chat')
        if status.get('ready') is not True:
            raise ValueError('Dashboard is reachable but Conversation is not ready.')
        return {'ready': True, 'queued': status.get('queued'), 'busy': status.get('busy')}
    check('dashboard and Conversation', dashboard)

    def metadata():
        status = get(f'http://127.0.0.1:{port}/api/state')
        if status.get('model_status') != 'ready':
            raise ValueError(status.get('model_detail') or 'Model telemetry is not ready yet.')
        return {'model_status': status['model_status'], 'model': status.get('model')}
    check('dashboard model status', metadata)

    def dashboard_config():
        from hanni.config.loader import load_config
        cfg = load_config(Path(root) / 'config', data_dir=state,
                          env={'HANNI_MODEL_CONFIG': str(state / 'models.dashboard.yaml')})
        return {'id': cfg.models.supervisor.id, 'api_model': cfg.models.supervisor.api_model}
    check('dashboard configuration', dashboard_config)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8311)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    results = diagnose(args.root, args.port)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f'HANNI: http://localhost:{args.port}')
        for item in results:
            print(('PASS' if item['ok'] else 'FAIL') + '  ' + item['check'] + ': ' + str(item['detail']))
    return 0 if all(item['ok'] for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())

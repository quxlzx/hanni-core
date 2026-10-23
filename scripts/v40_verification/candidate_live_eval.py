"""Existing unregistered HANNI 4B candidate, isolated endpoint; no primary swap."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).parent)]
from hanni.config.loader import load_config
from hanni.models.manager import ModelManager
from sealed_live_eval import local_request, grade


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', type=Path, required=True)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output, weights, campaign = args.output.resolve(), args.weights.resolve(), args.campaign.resolve()
    if not output.is_relative_to((ROOT / 'data/v40-verification').resolve()) or output.exists() or not weights.is_file():
        raise SystemExit('Existing weights and new protected evidence required.')
    output.mkdir(parents=True)
    encoded = (campaign / 'protocol.json').read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    assert digest == (campaign / 'protocol.sha256').read_text().strip()
    protocol = json.loads(encoded)
    config = load_config(ROOT / 'config', data_dir=output / 'state', env={})
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    spec = replace(config.models.supervisor, id='candidate', model_file=weights.name,
        api_model='hanni4b-candidate', endpoint=f'http://127.0.0.1:{port}/v1', keep_loaded=False)
    config = replace(config, models=replace(config.models, models=(spec,)))
    manager = ModelManager(config, model_files={'candidate': str(weights)}, startup_timeout=180)
    process = None
    metadata = {'registered_production_endpoint': False, 'primary_changed': False,
                'weights_file': weights.name, 'weights_bytes': weights.stat().st_size,
                'protocol_sha256': digest, 'profile': 'same default16K q8KV temperature0; owned separate endpoint'}
    rows = []
    try:
        entry = manager.ensure_loaded('candidate')
        process = entry.process
        assert process is not None
        metadata.update(owned_pid=process.pid, runtime_command=entry.command)
        (output / 'ownership.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
        for case in protocol['cases']:
            payload = {'model': spec.api_model, 'messages': [{'role': 'system', 'content': protocol['system']},
                {'role': 'user', 'content': case['prompt']}], **protocol['settings']}
            row = {'case_id': case['id'], 'split': case['split'], 'category': case['category']}
            try:
                began = time.perf_counter()
                response = local_request(spec, payload)
                assert response['model'] == spec.api_model
                row.update(response=response, latency_ms=(time.perf_counter() - began) * 1000, grading=grade(response, case))
            except Exception as error:
                row.update(error_class=type(error).__name__, grading={'passed': False})
            rows.append(row)
            (output / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
            print(json.dumps({'case': case['id'], 'passed': row['grading']['passed'], 'milliseconds': round(row.get('latency_ms', 0), 1)}), flush=True)
    except Exception as error:
        metadata.update(status='BLOCKED', error_class=type(error).__name__, error=str(error))
        print(json.dumps({'status': 'BLOCKED', 'error_class': type(error).__name__}), flush=True)
    finally:
        manager.close()
        metadata.update(owned_process_closed=process is None or process.poll() is not None, finished_at=time.time())
        (output / 'closed.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
        print(json.dumps({'owned_process_closed': metadata['owned_process_closed']}), flush=True)


if __name__ == '__main__':
    main()

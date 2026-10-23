"""Live auto-policy regression with currently unavailable remotes excluded."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(Path(__file__).parent)]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
from hanni.models.collaboration import CollaborationEngine
from single_baseline import grade


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--paired', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT/'data/v41-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    data = (args.paired/'supplementary.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == (args.paired/'supplementary.sha256').read_text().strip()
    supplementary = json.loads(data)
    data = (args.campaign/'protocol.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == supplementary['original_protocol_sha256']
    protocol = json.loads(data)
    state = output/'state'
    (state/'model-routing').mkdir(parents=True)
    with sqlite3.connect(f'file:{ROOT / "data/model-routing/profiles.sqlite3"}?mode=ro', uri=True) as source:
        with sqlite3.connect(state/'model-routing/profiles.sqlite3') as target: source.backup(target)
    config = load_config(ROOT/'config', env={})
    registry = ComputeRegistry(ROOT/'data')
    compute = ComputeScheduler(registry)
    engine = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=state)
    collaboration = CollaborationEngine(engine)
    calls = []
    original = compute.transport.request
    def observe(worker, method, path, **options):
        if worker['node_id'] != 'local': calls.append((worker['worker_id'], method, path))
        return original(worker, method, path, **options)
    compute.transport.request = observe
    rows = []
    try:
        # A fresh original loopback probe, not fabricated model telemetry.
        row = next(r for r in engine._inventory() if r['local'])
        engine.observations[row['endpoint_id']] = engine._probe_local(row)
        assert engine.observations[row['endpoint_id']]['status'] == 'healthy'
        for case in supplementary['routine']:
            messages = [{'role': 'system', 'content': protocol['system']}, {'role': 'user', 'content': case['prompt']}]
            request = ModelRequest(task_category='conversation', complexity='simple', output_tokens=384,
                                   privacy_categories=frozenset({'synthetic'}))
            def verify(text):
                passed = grade(text, case['expected'])['passed']
                return {'status': 'VERIFIED' if passed else 'UNVERIFIED', 'scope': 'sealed_synthetic_lookup',
                        'checks': {'exact_oracle_match': passed}}
            for mode in ['fixed', 'auto']:
                began = time.perf_counter()
                telemetry = {}
                result = {'case_id': case['id'], 'mode': mode, 'passed': False}
                try:
                    if mode == 'fixed':
                        text = engine.execute(messages, request=request, endpoint_id='local:supervisor', max_fallbacks=0,
                            telemetry=telemetry, **protocol['settings'])
                        result.update(response=text, tokens=telemetry.get('tokens'), participants=1)
                    else:
                        run = collaboration.run(messages, request=request, preference='auto', verify=verify, **protocol['settings'])
                        text = run['selected_output']
                        result.update(response=text, collaboration=run, participants=len(run['participants']))
                    result['passed'] = grade(text, case['expected'])['passed']
                except Exception as error: result['error_class'] = type(error).__name__
                result['latency_ms'] = (time.perf_counter()-began)*1000
                rows.append(result)
                print(json.dumps({k: result.get(k) for k in ('case_id','mode','passed','latency_ms','participants','error_class')}), flush=True)
        (output/'results.json').write_text(json.dumps({'rows': rows, 'remote_transport_calls': calls,
            'scope': 'Original4B real responses. Registered remotes remain unavailable with unknown resources; no sharing/admission bypass.'}, indent=2), encoding='utf8')
    finally:
        engine.close(); compute.close()


if __name__ == '__main__': main()

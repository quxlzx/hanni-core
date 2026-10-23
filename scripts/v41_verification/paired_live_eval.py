"""Real fixed4B / V4 sequential / V4.1 parallel comparison on sealed cases.

Only predefined recovery rows inject secondary transport failures. All remaining
responses use existing weights and production routing/collaboration primitives.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(Path(__file__).parent)]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.compute.registry import ComputeError
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
from hanni.models.client import LlamaCppClient
from hanni.models.collaboration import CollaborationEngine, CollaborationLimits
from single_baseline import grade

GPU_PROGRAM = """import csv,json,subprocess,time
p=subprocess.run(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
rows=[]
if p.returncode==0:
 for r in csv.reader(p.stdout.splitlines()):
  rows.append({'id':r[0].strip(),'name':r[1].strip(),'total_MiB':int(r[2]),'used_MiB':int(r[3]),'utilization_percent':int(r[4])})
print(json.dumps({'sampled_at':time.time(),'gpus':rows,'exit_code':p.returncode}))
"""


def protocol(args):
    campaign = args.campaign.resolve()
    encoded = (campaign/'protocol.json').read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    assert digest == (campaign/'protocol.sha256').read_text().strip()
    supplementary = {'original_protocol_sha256': digest, 'task_changes': False,
        'mode_order_per_case': ['fixed_primary', 'v4_sequential', 'v41_parallel'],
        'fixed_primary': 'Original primary pinned, zero fallback; trusted same exact oracle checks.',
        'v4_sequential': 'Original V4 execute with configured maximum2fallbacks and same exact oracle.',
        'v41_parallel': 'Production CollaborationEngine explicitparallel maximum3participants/concurrency2; same exact oracle.',
        'eligibility': 'Protected synthetic sharing/current runtime proofs; unavailable endpoints excluded; no forced model assignment.',
        'resource_sampling': 'Actual GPU total/used VRAM and utilization via bounded read-only SSH every1s plus command duration; shared loaded residency included in all modes. Sampled maxima are not true peak process consumption; energy unknown.',
        'routine': [{'id': 'routine-'+str(i), 'prompt': 'Synthetic stored value item'+str(i)+'='+str(i+11)+'. Return {"value":INTEGER} for item'+str(i)+'.', 'expected': {'value': i+11}} for i in range(5)]}
    path = args.output.resolve()
    assert path.is_relative_to((ROOT/'data/v41-verification').resolve())
    if args.seal:
        assert not path.exists()
        path.mkdir(parents=True)
        data = json.dumps(supplementary, indent=2, sort_keys=True).encode()
        (path/'supplementary.json').write_bytes(data)
        (path/'supplementary.sha256').write_text(hashlib.sha256(data).hexdigest())
        print(json.dumps({'sealed': True, 'task_changes': False, 'sha256': hashlib.sha256(data).hexdigest()}))
        return None
    data = (path/'supplementary.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == (path/'supplementary.sha256').read_text().strip()
    assert json.loads(data) == supplementary
    return json.loads(encoded), supplementary, digest, path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    values = protocol(args)
    if values is None: return
    sealed, supplementary, digest, output = values
    results_path = output/'results.jsonl'
    if results_path.exists(): raise SystemExit('Preserve prior measured evidence.')
    state = output/'state'
    (state/'model-routing').mkdir(parents=True)
    # Read-only backup of existing independently measured V4 proofs/profiles;
    # new holdout outcomes never enter selection profiles during this campaign.
    with sqlite3.connect(f'file:{ROOT / "data/model-routing/profiles.sqlite3"}?mode=ro', uri=True) as original:
        with sqlite3.connect(state/'model-routing/profiles.sqlite3') as target:
            original.backup(target)
    config = load_config(ROOT/'config', env={})
    registry = ComputeRegistry(ROOT/'data')
    compute = ComputeScheduler(registry)
    adaptive = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=state)
    collaboration = CollaborationEngine(adaptive, limits=CollaborationLimits(max_participants=3))
    # Reuse previously measured immutable file digest cache, rechecking remote
    # stat identities in the actual transport. No change to protected deployment.
    import ast
    cache = json.loads((ROOT/'data/v40-verification/identity-prepared-20261009-b/runtime-file-cache.json').read_text())
    compute.transport.identity_file_cache = {ast.literal_eval(k): v for k, v in cache.items()}
    observations = []
    observation_lock = threading.Lock()
    original_chat = LlamaCppClient.chat
    original_request = compute.transport.request
    fault = {'value': None}
    def observed_chat(client, messages, **options):
        usage = options.setdefault('usage', {})
        began = time.perf_counter()
        try:
            answer = original_chat(client, messages, **options)
            with observation_lock:
                observations.append({'endpoint_id': 'local:'+client.spec.id, 'real_inference': True,
                    'tokens': deepcopy(usage), 'latency_ms': (time.perf_counter()-began)*1000, 'output': answer})
            return answer
        except Exception:
            with observation_lock:
                observations.append({'endpoint_id': 'local:'+client.spec.id, 'real_inference': True,
                    'tokens': deepcopy(usage), 'latency_ms': (time.perf_counter()-began)*1000, 'partial_or_error': True})
            raise
    def observed_request(worker, method, path, **options):
        inference = method == 'POST' and path == '/v1/chat/completions'
        if inference and fault['value'] == 'secondary_unavailable':
            with observation_lock:
                observations.append({'endpoint_id': 'worker:'+worker['worker_id'], 'real_inference': False,
                                     'injected_fault': fault['value'], 'tokens': None})
            raise ComputeError('Predefined verifier secondary unavailable fixture.')
        if inference and fault['value'] == 'secondary_invalid':
            response = {'model': worker['model_id'], 'choices': [{'finish_reason': 'stop', 'message': {'content': '{"unknown":true}'}}]}
        else:
            response = original_request(worker, method, path, **options)
        if inference:
            with observation_lock:
                observations.append({'endpoint_id': 'worker:'+worker['worker_id'], 'real_inference': fault['value'] is None,
                    'tokens': response.get('usage'), 'injected_fault': fault['value'], 'response': deepcopy(response)})
        return response
    compute.transport.request = observed_request
    node = registry.node(registry.worker('athena-p40')['node_id'])
    address = compute.transport._address(node)
    def sample_gpu(rows, stop):
        while not stop.is_set():
            began = time.time()
            try:
                response = subprocess.run(compute.transport._ssh(node, address)+['python3 -'], input=GPU_PROGRAM.encode(),
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=6,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                sample = json.loads(response.stdout) if response.returncode == 0 else {'error_class': 'TelemetryExitError'}
            except Exception as error:
                sample = {'error_class': type(error).__name__}
            sample.update(local_sample_started_at=began, sample_command_ms=(time.time()-began)*1000)
            rows.append(sample)
            stop.wait(1)
    def execute(case, mode, *, routine=False):
        adaptive.refresh()
        observations.clear()
        fault['value'] = case.get('fault') if not routine else None
        messages = [{'role': 'system', 'content': sealed['system']}, {'role': 'user', 'content': case['prompt']}]
        request = ModelRequest(task_category=case.get('task_category', 'conversation'), complexity='simple' if routine else 'complex',
            privacy_categories=frozenset({'synthetic'}), output_tokens=384, capabilities=frozenset({'text'}))
        def verification(text):
            passed = grade(text, case['expected'])['passed']
            return {'status': 'VERIFIED' if passed else 'UNVERIFIED', 'scope': 'exact_sealed_synthetic_oracle',
                    'checks': {'exact_oracle_match': passed}}
        gpu_samples = []
        stop = threading.Event()
        sampler = threading.Thread(target=sample_gpu, args=(gpu_samples, stop), daemon=True)
        sampler.start()
        began = time.perf_counter()
        row = {'case_id': case['id'], 'category': case.get('category', 'routine'), 'mode': mode, 'protocol_sha256': digest,
               'passed': False, 'fault_fixture': fault['value'], 'preflight_health_identity_refresh_in_timing': False}
        try:
            if mode == 'v41_parallel' or mode == 'routine_auto':
                response = collaboration.run(messages, request=request, preference='auto' if routine else 'parallel',
                    verify=verification, context_refs=[{'synthetic_case': case['id'], 'protocol_sha256': digest}], **sealed['settings'])
                row.update(collaboration=response, response=response['selected_output'],
                           passed=response['final_verification']['status'] == 'VERIFIED')
            else:
                answer = adaptive.execute(messages, request=request, validator=lambda text: verification(text)['status'] == 'VERIFIED',
                    **({'endpoint_id': 'local:supervisor', 'max_fallbacks': 0} if mode in {'fixed_primary', 'routine_fixed'} else {}),
                    **sealed['settings'])
                row.update(response=answer, passed=verification(answer)['status'] == 'VERIFIED')
        except Exception as error:
            row['error_class'] = type(error).__name__
        row['latency_ms'] = (time.perf_counter()-began)*1000
        stop.set(); sampler.join(7)
        row.update(inferences=deepcopy(observations), gpu_samples=gpu_samples,
            generated_tokens_known=sum(r['tokens'].get('completion_tokens', 0) for r in observations if isinstance(r.get('tokens'), dict)),
            all_token_counts_known=all(isinstance(r.get('tokens'), dict) and type(r['tokens'].get('completion_tokens')) is int for r in observations))
        if row.get('response') is not None: row['grading'] = grade(row['response'], case['expected'])
        with results_path.open('a', encoding='utf8') as stream:
            stream.write(json.dumps(row)+'\n')
        print(json.dumps({'case': case['id'], 'mode': mode, 'passed': row['passed'], 'milliseconds': round(row['latency_ms'], 1),
                          'inferences': len(observations), 'tokens_known': row['generated_tokens_known'], 'error': row.get('error_class')}), flush=True)
    try:
        adaptive.refresh()
        (output/'initial-router.json').write_text(json.dumps(adaptive.snapshot(), indent=2), encoding='utf8')
        with patch.object(LlamaCppClient, 'chat', observed_chat):
            for case in sealed['cases']:
                for mode in supplementary['mode_order_per_case']:
                    execute(case, mode)
            for case in supplementary['routine']:
                execute(case, 'routine_fixed', routine=True)
                execute(case, 'routine_auto', routine=True)
        (output/'final-router.json').write_text(json.dumps(adaptive.snapshot(), indent=2), encoding='utf8')
    finally:
        adaptive.close(); compute.close()


if __name__ == '__main__':
    main()

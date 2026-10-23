"""Publish measured synthetic evidence through protected engineering APIs only."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src')]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine

MODELS = [
    '/home/user/Strata-data/models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf',
    '/home/user/Strata-data/models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf',
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['prepare', 'publish'], required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--capabilities', type=Path)
    p.add_argument('--context', type=Path)
    p.add_argument('--identity-prepared', type=Path)
    args = p.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/v40-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    config = load_config(ROOT / 'config', env={})
    compute = ComputeScheduler(ComputeRegistry(ROOT / 'data'))
    engine = AdaptiveModelEngine(config, compute_scheduler=compute)
    try:
        if args.identity_prepared:
            prepared = args.identity_prepared.resolve()
            assert prepared.is_relative_to((ROOT / 'data/v40-verification').resolve())
            cache = json.loads((prepared / 'runtime-file-cache.json').read_text())
            # Every cached digest remains subject to a fresh remote stat check.
            compute.transport.identity_file_cache = {ast.literal_eval(k): v for k, v in cache.items()}
        if args.mode == 'prepare':
            worker = compute.registry.worker('wonyoung-strata')
            node = compute.registry.node(worker['node_id'])
            import subprocess
            program = "import pathlib,json; root=pathlib.Path('/home/user/Strata'); files=[str(p) for p in root.rglob('*.so') if len(p.relative_to(root).parts)<=5 and p.is_file() and not p.is_symlink()]; print(json.dumps({'backend_files':['/home/user/Strata/serve/server.py']+sorted(files)[:60]}))"
            r = subprocess.run(compute.transport._ssh(node, compute.transport._address(node)) + ['python3 -'],
                input=program.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
            assert r.returncode == 0 and len(r.stdout) <= 32768
            source = json.loads(r.stdout)
            inspection = {'model_files': MODELS, 'backend_files': source['backend_files'],
                          'purpose': 'Read-only explicit existing GGUF/model backend fingerprints; no configuration contents read.'}
            encoded = json.dumps(inspection, sort_keys=True).encode()
            (output / 'identity-files.json').write_bytes(encoded)
            engine.register_identity_files('worker:wonyoung-strata', model_files=MODELS,
                backend_files=source['backend_files'], evidence_sha256=hashlib.sha256(encoded).hexdigest(),
                environment='independent read-only existing model and installed backend full-file SHA256')
        began = time.perf_counter()
        engine.refresh()
        # Full hashing can outlast the short health lease; re-probe without
        # changing its timestamp or bypassing the actual server health checks.
        if any(r['health'] != 'healthy' for r in engine.snapshot()['endpoints']):
            engine.refresh()
        identities = {r['endpoint_id']: engine.endpoint_identity(r['endpoint_id']) for r in engine.snapshot()['endpoints']}
        (output / 'identities.json').write_text(json.dumps(identities, indent=2), encoding='utf8')
        if args.mode == 'publish':
            cap_encoded = args.capabilities.read_bytes()
            caps = json.loads(cap_encoded)
            contexts = json.loads((args.context / 'results.json').read_text())
            local_context = next(r for r in caps if r['endpoint_id'] == 'local:supervisor' and r['kind'] == 'long_context')
            assert local_context['passed']
            for endpoint, identity in identities.items():
                probes = [r for r in caps if r['endpoint_id'] == endpoint and r.get('passed')]
                capabilities = ['text'] + [r['kind'] for r in probes if r['kind'] in {'structured_json', 'tool_calling'}]
                measured_context = (local_context if endpoint.startswith('local:') else
                    next((r for r in contexts if 'worker:' + r['worker_id'] == endpoint), None))
                kwargs = {}
                if measured_context and measured_context['passed']:
                    kwargs = {'context_tokens': measured_context['target_tokens'],
                        'observed_prompt_tokens': measured_context['observed_prompt_tokens'], 'retrieval_passed': True}
                metadata = {'structured_output_formats': ['json_object'] if 'structured_json' in capabilities else [],
                            'tool_calling_formats': ['openai_function'] if 'tool_calling' in capabilities else [],
                            'vision_input_formats': []}
                if endpoint in {'worker:athena-p40', 'worker:athena-p6000'}:
                    metadata.update(architecture='qwen35', quantization='Q4_K_S')
                elif endpoint == 'worker:wonyoung-strata':
                    metadata.update(architecture='qwen4exp', quantization='IQ3_S')
                elif endpoint == 'local:supervisor':
                    metadata.update(architecture='qwen35', quantization='Q4_K_M')
                engine.record_capability_evidence(endpoint, identity=identity, capabilities=capabilities,
                    evidence_sha256=hashlib.sha256(cap_encoded).hexdigest(),
                    environment='real synthetic temp0 thinkingoff; actual JSON-object/native-function probes and counted context',
                    metadata=metadata, **kwargs)
                if endpoint.startswith('worker:') and kwargs:
                    worker_id = endpoint.removeprefix('worker:')
                    record = measured_context
                    compute.registry.record_context_verified(worker_id,
                        target_tokens=record['target_tokens'], prompt_tokens=record['observed_prompt_tokens'],
                        model_id=compute.registry.worker(worker_id)['model_id'],
                        prompt_sha256=record['prompt_sha256'],
                        response_sha256=hashlib.sha256(json.dumps(record['response'], sort_keys=True).encode()).hexdigest())
            # All fixed and adaptive holdout decisions were sealed before this import.
            baseline = ROOT / 'data/v40-verification/prospective-20261009-a/baseline-results.jsonl'
            for line in baseline.read_text().splitlines():
                row = json.loads(line)
                response = row.get('response', {})
                timings = response.get('timings', {})
                engine.record_evaluation(row['endpoint_id'], identity=identities[row['endpoint_id']],
                    task_category=row['category'], correct=row['grading']['passed'],
                    verified_success=row['grading']['passed'], latency_ms=row['latency_ms'],
                    evidence_sha256=hashlib.sha256(line.encode()).hexdigest(),
                    environment='sealed synthetic ' + row['split'] + '; temp0 thinkingoff output384; tiny sample after A/B sealing',
                    generation_tps=timings.get('predicted_per_second'), prompt_tps=timings.get('prompt_per_second'),
                    evaluation_id='v40-real:' + row['endpoint_id'] + ':' + row['case_id'])
        snapshot = engine.snapshot()
        (output / 'snapshot.json').write_text(json.dumps(snapshot, indent=2), encoding='utf8')
        (output / 'runtime-file-cache.json').write_text(json.dumps({str(k): v for k,v in compute.transport.identity_file_cache.items()}, indent=2), encoding='utf8')
        print(json.dumps({'mode': args.mode, 'elapsed_seconds': round(time.perf_counter()-began, 2),
                          'endpoints': [{k: r.get(k) for k in ('endpoint_id','health','max_context_verified','capabilities')} for r in snapshot['endpoints']]}), flush=True)
    finally:
        engine.close()
        compute.close()


if __name__ == '__main__':
    main()

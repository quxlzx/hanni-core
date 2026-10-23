"""Expose prompt-proof/combined-allocation growth boundary without any launch."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from hanni.compute.registry import ComputeError
from scripts.campaign6_verification.boundary_controls import environment, replace, DEVICE

class NoLaunchBoundary(Exception):
    pass

def run(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign6-verifier').resolve()):
        raise ValueError('Use a fresh verifier-owned evidence directory')
    output.mkdir(parents=True)
    calls = []
    with environment(output / 'state') as env:
        worker = env.data['workers'][0]
        worker['startup'] = {'authorized': True, 'kind': 'llama_cpp', 'executable': '/opt/owned/llama-server', 'model_file': '/opt/owned/synthetic.gguf', 'gpu_device': DEVICE, 'context': 8192}
        replace(env)
        env.registry.record_context_verified('probe-worker', target_tokens=8191, prompt_tokens=8100, model_id='controlled-protocol-model', prompt_sha256='a' * 64, response_sha256='b' * 64)
        worker['context_configured'] = 16384
        worker['startup']['context'] = 16384
        replace(env)
        prior = env.registry.prior_verified_context('probe-worker')

        def no_process(command, **kwargs):
            calls.append({'command_count': len(command), 'operation': 'occupancy_check' if len(calls) == 0 else 'launch_blocked_by_fixture'})
            if len(calls) == 1:
                return SimpleNamespace(returncode=3)
            raise NoLaunchBoundary('No process is created by this independent probe')
        with patch.object(env.transport, 'health', lambda worker: {'status': 'unhealthy'}), patch.object(env.transport, '_ssh', lambda *args, **kwargs: ['controlled-leaf']), patch.object(env.transport, '_address', lambda node: '' + '.'.join(('10', '42', '0', '7')) + ''), patch('hanni.compute.transport.subprocess.run', no_process):
            try:
                env.transport._start(env.worker())
                outcome = {'unexpected_return': True}
            except (ComputeError, NoLaunchBoundary) as exc:
                outcome = {'class': type(exc).__name__, 'message': str(exc)}
    result = {'scope': 'Controlled original launch preflight only; no real service/process/SSH/model action', 'prior_total_allocation': 8192, 'prior_prompt_proof': prior, 'minimum_reserved_output': 1, 'requested_next_total_allocation': 16384, 'old_growth_required_prompt_proof': 8192, 'outcome': outcome, 'controlled_leaf_calls': calls, 'actual_launches': 0, 'source': {'src/hanni/compute/transport.py': hashlib.sha256((ROOT / 'src/hanni/compute/transport.py').read_bytes()).hexdigest()}}
    (output / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)

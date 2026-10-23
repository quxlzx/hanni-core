"""Replace overlapping private compute endpoints with the ZIP's deployments.

Only local configuration changes; services remain under Cluster Control. Existing
sharing permissions and scheduler policy are retained. Previous configuration is
saved before writing, and rerunning does not replace that backup.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from hanni.compute.registry import validate_deployment


def migrate(raw):
    result = deepcopy(raw)
    nodes = {node['id'] for node in result.get('nodes', [])}
    if not {'hanni', 'wonyoung'} <= nodes:
        raise ValueError('Configure HANNI and Wonyoung SSH nodes before importing.')
    existing = {worker['worker_id']: worker for worker in result.get('workers', [])}
    definitions = (
        ('athena-p6000', 'hanni', 'Nex-N2-mini', 'Quadro P6000', 'nex-n2-mini', 8102, 32768,
         '/home/user/models/nex/Nex-N2-mini-IQ4_XS.gguf',
         '/home/user/hanni-bench/llama.cpp/build-cuda/bin/llama-server'),
        ('athena-p40', 'hanni', 'Mellum 2.1', 'Tesla P40', 'mellum-2.1', 8103, 65536,
         '/home/user/models/mellum/Mellum2.1-12B-A2.5B-Thinking-Q4_K_M.gguf',
         '/home/user/hanni-bench/llama.cpp/build-cuda/bin/llama-server'),
        ('hanni-swift', 'hanni', 'Swift 1.5', 'RX 9060 XT', 'swift-1.5', 8101, 32768,
         '/home/user/models/swift/Swift-1.5-Qwen3.8-27b.i1-IQ3_S.gguf',
         '/home/user/HANNI_BENCH_LINUX/llama.cpp/build-vulkan/bin/llama-server'),
        ('wonyoung-strata', 'wonyoung', 'Flash-Next', 'RX 7900 XT', 'qwen3.8-flash-next-iq3_s',
         8080, 131072, None, None),
    )
    for key, node, label, gpu, model, port, context, weights, binary in definitions:
        prior = existing.get(key, {})
        worker = {'worker_id': key, 'node_id': node, 'label': label, 'gpu': gpu,
                  'model_id': model, 'protocol': 'strata_openai' if weights is None else 'llama_cpp',
                  'remote_port': port, 'enabled': prior.get('enabled', True),
                  'concurrency': 1, 'interactive_reserve': 0,
                  'capabilities': prior.get('capabilities', ['analysis', 'structured_json']),
                  'allowed_categories': prior.get('allowed_categories', ['synthetic']),
                  'context_configured': context,
                  'model_context_limit': 131072 if weights is None or key == 'athena-p40' else 262144}
        if weights:
            worker['startup'] = {'authorized': False, 'kind': 'llama_cpp', 'executable': binary,
                                 'model_file': weights, 'context': context,
                                 'cache_type_k': 'q8_0', 'cache_type_v': 'q8_0'}
        else:
            worker['auth_config_file'] = prior.get('auth_config_file', '/home/user/Strata/strata-iq3_s.json')
            worker['identity_model_roots'] = prior.get('identity_model_roots', ['/home/user/Strata-data/models/IQ3_S'])
            worker['startup'] = {'authorized': False, 'kind': 'strata',
                                 'installation_dir': '/home/user/Strata'}
        existing[key] = worker
    result['workers'] = list(existing.values())
    return validate_deployment(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    path = args.data_dir / 'compute' / 'deployment.json'
    raw = path.read_text(encoding='utf-8-sig')
    updated = migrate(json.loads(raw))
    backup = path.with_name('deployment.before-control-center.json')
    if not backup.exists():
        backup.write_text(raw, encoding='utf-8')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(updated, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
    print('Imported four model deployments. Existing sharing permissions and scheduler policy retained.')


if __name__ == '__main__':
    main()

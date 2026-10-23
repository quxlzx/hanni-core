"""Manager imports independently sealed actual retrieval proof, never metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute.registry import ComputeRegistry, ComputeError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path, nargs='+')
    args = parser.parse_args()
    sealed = ROOT / 'data/v37-verification/sealed/protocol.json'
    protocol = json.loads(sealed.read_text(encoding='utf-8'))
    protocol_sha = hashlib.sha256(sealed.read_bytes()).hexdigest()
    registry = ComputeRegistry(ROOT / 'data')
    try:
        for path in args.evidence:
            path = path.resolve()
            if not path.is_relative_to((ROOT / 'data/v37-verification/context').resolve()) or path.is_symlink():
                raise ComputeError('Only private independent context evidence can be reviewed.')
            row = json.loads(path.read_text(encoding='utf-8'))
            case = next(item for item in protocol['context_cases'] if item['target_context_tokens'] == row['stage'])
            expected = {item['key']: item['value'] for item in case['needles']}
            attempts = row['attempts']
            if (row['status'] != 'LIVE_PASS' or row['protocol_sha256'] != protocol_sha
                    or row['max_context_verified'] != row['stage'] or len(attempts) != case['repetitions']
                    or not all(attempt['passed'] and attempt['answer'] == expected and attempt['finish_reason'] == 'stop'
                               and .9 * row['stage'] <= attempt['runtime_prompt_tokens'] <= row['stage'] - 128
                               for attempt in attempts)):
                raise ComputeError('Independent context evidence did not satisfy its sealed retrieval oracle.')
            worker_id = row['worker_id']
            model_id = row['model_identity']['data'][0]['id']
            registry.record_context_verified(worker_id, target_tokens=row['stage'],
                prompt_tokens=min(attempt['runtime_prompt_tokens'] for attempt in attempts), model_id=model_id,
                prompt_sha256=row['prompt_sha256'], response_sha256=hashlib.sha256(
                    json.dumps([attempt['answer'] for attempt in attempts], sort_keys=True).encode()).hexdigest())
            print(json.dumps({'worker_id': worker_id, 'actual_context_verified': row['stage']}))
    finally:
        registry.close()


if __name__ == '__main__':
    main()

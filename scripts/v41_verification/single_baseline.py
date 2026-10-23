"""One original-model inference per prospective case, before collaboration."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from hanni.config.loader import load_config
from hanni.models.resource_manager import snapshot_resources
from hanni.workflows.verification import parse_evidence_json


def grade(text, expected):
    try:
        value = parse_evidence_json(text)
        return {'passed': value == expected, 'value': value}
    except Exception as error:
        return {'passed': False, 'error_class': type(error).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args()
    campaign = args.campaign.resolve()
    if not campaign.is_relative_to((ROOT/'data/v41-verification').resolve()):
        raise SystemExit('Protected campaign required.')
    encoded = (campaign/'protocol.json').read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    assert digest == (campaign/'protocol.sha256').read_text().strip()
    protocol = json.loads(encoded)
    output = campaign/'single-results.jsonl'
    if output.exists():
        raise SystemExit('Preserve prior measured evidence.')
    config = load_config(ROOT/'config', env={})
    spec = config.models.supervisor
    for case in protocol['cases']:
        messages = [{'role': 'system', 'content': protocol['system']}, {'role': 'user', 'content': case['prompt']}]
        resources = snapshot_resources()
        row = {'case_id': case['id'], 'category': case['category'], 'protocol_sha256': digest,
               'endpoint_id': 'local:'+spec.id, 'messages_sha256': hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
               'resources_before': {'ram_total_gb': resources.ram_total_gb, 'ram_used_gb': resources.ram_used_gb,
                    'gpus': [{'name': gpu.name, 'memory_total_mb': gpu.memory_total_mb, 'memory_used_mb': gpu.memory_used_mb} for gpu in resources.gpus]},
               'resources_scope': 'Host available/used capacity snapshot, not peak process consumption or energy.',
               'real_inference': False, 'grading': {'passed': False}}
        payload = {'model': spec.api_model, 'messages': messages, **protocol['settings'], 'stream': False,
                   'chat_template_kwargs': {'enable_thinking': False}}
        began = time.perf_counter()
        try:
            req = urllib.request.Request(spec.endpoint.rstrip('/')+'/chat/completions',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.load(response)
            assert result['model'] == spec.api_model
            choice = result['choices'][0]
            assert choice['finish_reason'] in {'stop', 'eos'}
            row.update(response=result, grading=grade(choice['message']['content'], case['expected']), real_inference=True)
        except Exception as error:
            row['error_class'] = type(error).__name__
        row['latency_ms'] = (time.perf_counter()-began)*1000
        with output.open('a', encoding='utf8') as stream:
            stream.write(json.dumps(row)+'\n')
        print(json.dumps({'case': case['id'], 'passed': row['grading']['passed'],
                          'milliseconds': round(row['latency_ms'], 1), 'error': row.get('error_class')}), flush=True)


if __name__ == '__main__':
    main()

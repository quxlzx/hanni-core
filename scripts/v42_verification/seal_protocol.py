"""Seal independent performance objectives before any implementation changes."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / 'data/v42-verification/prospective-20261009-a'
    output.mkdir(parents=True, exist_ok=False)
    protocol = {
        'version': 1,
        'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'predefined_objectives': [
            {'id': 'independent_worker_queue_latency', 'category': 'parallel_workflow',
             'measurement': 'Original ComputeScheduler, controlled HTTP endpoints, pinned busy A ahead of idle B',
             'success': 'P50 and P95 idle B end-to-end latency reduced by at least 50%; exact response and receipt unchanged',
             'scope': 'Controlled queue/workflow improvement; never a claim of GPU or model speed improvement'},
            {'id': 'profile_selection_overhead', 'category': 'adaptive_profile_read',
             'measurement': 'Original profile aggregation over 5000 explicit synthetic graded history rows, repeated reads',
             'success': 'P50 profile read latency reduced by at least 50%; complete aggregate identical and invalidation passes'},
        ],
        'repetitions': {'short': 5, 'long': 5, 'memory': 5, 'tool': 3, 'concurrent': 3,
                        'context_each': 3, 'queue_each': 7, 'profile': 15},
        'settings': {'temperature': 0, 'top_p': 1, 'max_tokens': 192,
                     'chat_template_kwargs': {'enable_thinking': False}},
        'model_configuration': 'Existing primary exactly as configured:16K context/parallel1/q8_0 KV/no download or weight replacement',
        'categories': ['short','long','tool','memory','concurrent','parallel_workflow','worker_disconnect',
                       'high_queue','long_context','interactive_contention'],
        'quality_oracle': 'Exact synthetic JSON/strings or original MCP VERIFIED receipt, never agreement/model confidence',
        'missing_metric_policy': 'Unknown remains null. Stage durations overlap and must not be summed blindly. Capacity snapshots are not peak process/VRAM allocation.',
        'cold_start_policy': 'Owned model load plus first request reported separately from repeated warm calls',
        'context_targets': [8192,16384],
        'unsupported_targets': [32768,65536,131072],
        'essential_context_policy': 'All three exact position needles required; no context elision/truncation',
        'cases': [
            {'id':'short','prompt':'Return only JSON: {"serial":8427,"available":false}.',
             'expected': {'serial':8427,'available':False}},
            {'id':'long','prompt':'Synthetic ledger: '+ '\n'.join(f'line {i:04d}: neutral calibration placeholder.' for i in range(400))+
             '\nAUTHORITATIVE_CODE=coral-8427\nReturn only {"code":"value"} using AUTHORITATIVE_CODE.',
             'expected': {'code':'coral-8427'}},
            {'id':'memory','query':'What is my synthetic calibration project dispatch code?',
             'record':'My synthetic calibration project dispatch code is coral-8427.',
             'prompt':'Using only the supplied historical record, return {"code":"value"} for my synthetic calibration project dispatch code.',
             'expected': {'code':'coral-8427'}},
        ],
    }
    encoded = json.dumps(protocol, sort_keys=True, indent=2).encode()
    (output/'protocol.json').write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    (output/'protocol.sha256').write_text(digest, encoding='utf8')
    print(json.dumps({'protocol_sha256':digest,'baseline_commit':protocol['baseline_commit'],'output':str(output)}))


if __name__ == '__main__': main()

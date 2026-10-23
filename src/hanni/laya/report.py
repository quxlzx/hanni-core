"""Aggregate-only status report; never outputs the request, memory, or prompt."""
import argparse
import collections
import json
from pathlib import Path
from .audit import default_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--audit-file', default=str(default_path()))
    a = p.parse_args()
    path = Path(a.audit_file).expanduser()
    if not path.exists():
        print('No shadow decisions recorded yet.')
        return
    labels = collections.defaultdict(collections.Counter)
    durations = []
    n = 0
    with path.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            durations.append(r['latency_ms'])
            for k, v in r.get('decisions', {}).items():
                if k == 'importance':
                    labels[k][str(round(float(v)))] += 1
                else:
                    labels[k][str(v)] += 1
    print(json.dumps({'evaluations': n,
                      'mean_inference_ms': round(sum(durations) / len(durations), 2) if durations else None,
                      'decision_counts': {k: dict(c) for k, c in labels.items()},
                      'memory_mutations': 0, 'shadow_only': True}, indent=2))

if __name__ == '__main__':
    main()

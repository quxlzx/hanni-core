"""Aggregate preserved receipts without changing frozen scoring or failures."""
import json
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def main():
    root = Path('data/phase3')
    read = lambda name: json.loads((root / name).read_text())
    comparison = read('heldout-final.json')
    summary = {'scope': comparison['scope'], 'freeze': read('../../evals/phase3/freeze.json'),
               'endpoint_status': comparison['endpoints'], 'comparison': {}}
    for endpoint in dict.fromkeys(row['endpoint'] for row in comparison['records']):
        rows = [row for row in comparison['records'] if row['endpoint'] == endpoint]
        kinds = {}
        for kind in dict.fromkeys(row['kind'] for row in rows):
            cohort = [row for row in rows if row['kind'] == kind]
            durations = [row['duration_ms'] for row in cohort if 'duration_ms' in row]
            kinds[kind] = {'passed': sum(row['correct'] for row in cohort), 'total': len(cohort),
                           'p50_ms': percentile(durations, .5), 'p95_ms': percentile(durations, .95)}
        summary['comparison'][endpoint] = {'passed': sum(row['correct'] for row in rows),
            'total': len(rows), 'by_kind': kinds,
            'failures': [row['id'] for row in rows if not row['correct']]}
    for filename in ('integrated-final.json', 'memory-fresh-final.json'):
        rows = read(filename)['records']
        summary[filename] = {'passed': sum(row['passed'] for row in rows), 'total': len(rows),
                            'failures': [row['id'] for row in rows if not row['passed']]}
    responsiveness = read('text-responsiveness.json')
    summary['text_responsiveness'] = {key: responsiveness[key] for key in
        ('latency', 'brevity', 'simple_task_success', 'required_tool_recall')}
    summary['cancellation_initial'] = {key: value for key, value in read('cancellation-live.json').items()
                                       if key != 'background_error'}
    summary['cancellation_followup'] = read('cancellation-followup.json')
    summary['not_measured'] = ['physical first audible answer', 'server queue latency',
        'Swift inference', 'live updated Control Center deployment', 'live calendar',
        'live restart/outage recovery', 'full background workflow concurrency']
    summary['acceptance'] = 'NOT ACCEPTED: inherited workflow completion/truthfulness gate remains failed'
    (root / 'results-summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary['comparison'], indent=2))


if __name__ == '__main__':
    main()

"""Append independently authored registry probes; never derive expectations from retrieval."""
import json
from pathlib import Path

from hanni.evals.routing import build_default_host, _domain
from hanni.mcp.host import classification, family_of


def main():
    root = Path('evals/routing')
    host = build_default_host()
    prompts = json.loads((root / 'registry_prompts.json').read_text(encoding='utf-8'))
    names = {d.name for d in host.registry.definitions()}
    assert set(prompts) == names, (names - prompts.keys(), prompts.keys() - names)
    path = root / 'cases.jsonl'
    original = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    rows = [r for r in original if not r['id'].startswith('REGISTRY-')]
    for row in rows:
        if row['family'] == 'blocked_writes':
            # Preserve the original observe-only policy regression cases even
            # as production explicitly enables existing app/media actions.
            row['allowed_actions'] = ['google_calendar.create']
    for name, queries in prompts.items():
        definition = host.registry.get(name)
        allowed = host._allowed(definition)
        for index, query in enumerate(queries):
            rows.append(dict(id=f'REGISTRY-{name}-{index+1}', family='registry_' + name.split('.')[0],
                query=query, expected_domain=_domain(name), expected_intent=name,
                mode='tools' if allowed else 'blocked',
                required=[name] if allowed else [], primary=name if allowed else None,
                blocked_capabilities=[] if allowed else [name],
                forbidden=[] if allowed else [name],
                expected_families=[family_of(name)],
                expected_classifications={name: classification(definition)},
                now='2026-09-22T10:00:00', tags=['registry_coverage']))
            diagnostic = {'process.top_cpu': 'cpu_pressure', 'process.top_memory': 'memory_pressure',
                          'gpu.memory': 'gpu_vram', 'gpu.top_processes': 'gpu_vram',
                          'process.top_disk_io': 'disk_io', 'system.performance': 'general_slowdown',
                          'model.status': 'model_runtime', 'system.event_errors': 'windows_errors'}
            if name in diagnostic:
                rows[-1]['expected_subintent'] = diagnostic[name]
    assert len({r['id'] for r in rows}) == len(rows)
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


if __name__ == '__main__':
    main()

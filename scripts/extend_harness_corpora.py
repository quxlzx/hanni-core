"""Add reviewed probes for existing workplace capabilities; preserve v1-v3."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = {
    'web.search': ['search the public web for battery recycling', 'web search recent battery research'],
    'screen.read_text': ['capture current screen text', 'read visible desktop text'],
    'reminder.create': ['create a persistent reminder', 'save a one-time reminder'],
}


def extend(path, rows):
    raw = path.read_text(encoding='utf-8')
    ids = {row['id'] for line in raw.splitlines() if line.strip() and (row := json.loads(line)).get('id')}
    new = [row for row in rows if row['id'] not in ids]
    if new:
        with path.open('a', encoding='utf-8', newline='') as stream:
            if not raw.endswith('\n'):
                stream.write('\n')
            for row in new:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')


def main():
    from hanni.evals.routing import build_default_host
    from hanni.evals.llm_coverage import fixture_for
    host = build_default_host(config_dir=ROOT / 'config')
    routing, scenarios, coverage = [], [], []
    for name, queries in QUERIES.items():
        definition = host.registry.get(name)
        facing = host._allowed(definition)
        for number, query in enumerate(queries, 1):
            identifier = f'HARNESS-LAYER-{name.upper().replace(".", "-")}-{number}'
            routing.append({'id': identifier, 'family': 'assistant_harness', 'query': query,
                'expected_domain': name.partition('.')[0], 'primary': name if facing else None,
                'required': [name] if facing else [], 'mode': 'tools' if facing else 'blocked',
                'blocked_capabilities': [] if facing else [name]})
            row = {'id': identifier, 'family': 'assistant_harness', 'query': query,
                'required_tools': [name] if facing else [], 'forbidden_tools': [] if facing else [name],
                'required_any_tools': [], 'results': {name: fixture_for(definition)} if facing else {}, 'claims': []}
            scenarios.append(row)
            if facing:
                coverage.append({**row, 'fixture_scope': 'schema_and_menu_only', 'risk_level': definition.risk_level,
                                 'side_effect': definition.side_effect, 'expected_schema': definition.argument_schema()})
    extend(ROOT / 'evals/routing/cases.jsonl', routing)
    extend(ROOT / 'evals/llm_tools/cases.jsonl', scenarios)
    source = ROOT / 'evals/llm_tools/capability_coverage_v3.jsonl'
    target = ROOT / 'evals/llm_tools/capability_coverage_v4.jsonl'
    old = source.read_bytes()
    additions = b''.join((json.dumps(row) + '\n').encode() for row in coverage)
    target.write_bytes(old + additions)
    (target.parent / 'capability_coverage_v4_migration.json').write_text(json.dumps({
        'source': source.name, 'target': target.name, 'source_sha256': hashlib.sha256(old).hexdigest(),
        'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'added_case_ids': [r['id'] for r in coverage],
        'preserved_source_bytes': len(old), 'reason': 'Two explicit source-selection probes for the existing web.search capability. Historical v1-v3 cases and oracles remain unchanged.'}, indent=2) + '\n')
    print('Added six routing/scenario probes and two model-facing schema probes; v1-v3 unchanged.')


if __name__ == '__main__':
    main()

"""Add reviewed probes for the six Teams read capabilities; preserve v1-v4."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = {
    'teams.teams': ['show me the list of teams I joined on Teams', 'what Microsoft Teams teams can I see'],
    'teams.channels': ['list the channels inside the Design team on Teams', 'what channels does the Marketing team have in Microsoft Teams'],
    'teams.channel_messages': ['what was posted in the Teams project channel', 'show me the channel posts in Microsoft Teams'],
    'teams.chat_messages': ['what did Alex say in our Teams chat', 'list my recent Teams chats'],
    'teams.chats': ['list the Teams chats I have', 'who has a Teams chat with me'],
    'teams.replies': ['show replies in the Teams thread', 'read the thread replies under that Teams channel post'],
}
FAMILY = 'teams_read'


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
    from datetime import datetime
    from hanni.evals.routing import build_default_host
    from hanni.evals.llm_coverage import fixture_for
    host = build_default_host(config_dir=ROOT / 'config')
    routing, scenarios, coverage = [], [], []
    for name, queries in QUERIES.items():
        definition = host.registry.get(name)
        if not host._allowed(definition):
            raise SystemExit(f'{name} is not model-facing; expected six exposed Teams readers.')
        for number, query in enumerate(queries, 1):
            identifier = f'TEAMS-READ-{name.upper().replace(".", "-")}-{number}'
            menu = host.route(query, now=datetime(2026, 9, 22, 10)).tools
            selected = [tool.capability_id for tool in menu]
            if name not in selected:
                raise SystemExit(f'{query!r} does not route to {name}: {selected}')
            routing.append({'id': identifier, 'family': FAMILY, 'query': query,
                'expected_domain': 'teams', 'expected_intent': 'teams_read',
                'primary': name if selected[0] == name else None,
                'required': [name], 'acceptable': sorted(QUERIES), 'mode': 'tools'})
            results = {tool.capability_id: fixture_for(host.registry.get(tool.capability_id)) for tool in menu}
            row = {'id': identifier, 'family': FAMILY, 'query': query,
                'required_tools': [name], 'required_any_tools': [], 'results': results, 'claims': []}
            scenarios.append(row)
            coverage.append({**row, 'fixture_scope': 'schema_and_menu_only', 'risk_level': definition.risk_level,
                             'side_effect': definition.side_effect, 'expected_schema': definition.argument_schema()})
    extend(ROOT / 'evals/routing/cases.jsonl', routing)
    extend(ROOT / 'evals/llm_tools/cases.jsonl', scenarios)
    source = ROOT / 'evals/llm_tools/capability_coverage_v4.jsonl'
    target = ROOT / 'evals/llm_tools/capability_coverage_v5.jsonl'
    old = source.read_bytes()
    additions = b''.join((json.dumps(row) + '\n').encode() for row in coverage)
    target.write_bytes(old + additions)
    (target.parent / 'capability_coverage_v5_migration.json').write_text(json.dumps({
        'source': source.name, 'target': target.name, 'source_sha256': hashlib.sha256(old).hexdigest(),
        'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'added_case_ids': [r['id'] for r in coverage],
        'preserved_source_bytes': len(old),
        'reason': 'Two routing probes, two LLM scenarios and two schema probes for each of the six model-facing Teams read capabilities. Historical v1-v4 cases and oracles remain unchanged.'}, indent=2) + '\n')
    print(f'Added {len(routing)} routing cases, {len(scenarios)} LLM scenarios and {len(coverage)} coverage probes; v1-v4 unchanged.')


if __name__ == '__main__':
    main()

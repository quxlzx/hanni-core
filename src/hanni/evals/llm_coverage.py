"""Audit model-facing capability coverage without executing tools or a model."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from hanni.evals.llm_tools import audit_scenarios, corpus_sha256, load_scenarios
from hanni.evals.routing import build_default_host

DEFAULT_COVERAGE_CASES = Path('evals/llm_tools/capability_coverage_v3.jsonl')


def fixture_for(definition):
    """A schema-shaped observation, never a call to the capability handler."""
    defaults = {'array': [], 'object': {}, 'integer': 0, 'number': 0.0,
                'boolean': False, 'string': '', 'file|folder': 'file', 'accepted': 'accepted'}
    # Optional describes field presence, not a nullable value. When supplying
    # a shape-only field, use a value of its declared type. Nullable unions can
    # safely use null without enumerating every primitive union spelling.
    data = {key: None if 'null' in kind.removeprefix('optional ').split('|')
            else defaults[kind.removeprefix('optional ')]
            for key, kind in definition.output_schema.items()}
    return {'name': definition.name, 'ok': True,
            'message': 'Synthetic schema probe; no capability was executed.',
            'data': data}


def build_coverage_cases(host, prompts):
    """Use the existing two curated registry probes per exposed capability."""
    rows = []
    for definition in sorted(host.registry.definitions(), key=lambda item: item.name):
        if not host._allowed(definition):
            continue
        queries = prompts.get(definition.name, ())
        if len(queries) < 2:
            raise ValueError(f'{definition.name} needs two independent probes')
        for number, query in enumerate(queries[:2], 1):
            menu = host.route(query, now=datetime(2026, 9, 22, 10)).tools
            results = {tool.capability_id: fixture_for(host.registry.get(tool.capability_id))
                       for tool in menu}
            rows.append({'id': f'COV-{definition.name.replace(".", "-").upper()}-{number:02d}',
                         'family': 'capability_coverage', 'query': query,
                         'required_tools': [definition.name], 'required_any_tools': [],
                         'results': results,
                         'claims': [], 'risk_level': definition.risk_level,
                         'side_effect': definition.side_effect,
                         'expected_schema': definition.argument_schema(),
                         'fixture_scope': 'schema_and_menu_only'})
    return rows


def audit_coverage(host, cases):
    counts: Counter[str] = Counter()
    for case in cases:
        # An any-of group is evidence of menu reachability, not proof that
        # each alternative was actually selected by the model.
        counts.update(set(case.get('required_tools', ())))
    rows = []
    coverage_errors = []
    definitions = {item.name: item for item in host.registry.definitions()}
    for case in cases:
        for name in case.get('required_tools', ()):
            definition = definitions.get(name)
            if definition is None or not host._allowed(definition):
                coverage_errors.append(f"{case['id']}: {name} is unavailable to the model")
                continue
            fixture = case.get('results', {}).get(name)
            if not fixture or fixture.get('name') != name:
                coverage_errors.append(f"{case['id']}: missing synthetic result for {name}")
            elif case.get('fixture_scope') == 'schema_and_menu_only' and set(fixture.get('data', {})) != set(definition.output_schema):
                coverage_errors.append(f"{case['id']}: result schema drift for {name}")
            if case.get('fixture_scope') == 'schema_and_menu_only':
                if case.get('expected_schema') != definition.argument_schema():
                    coverage_errors.append(f"{case['id']}: argument schema drift for {name}")
                if case.get('risk_level') != definition.risk_level or case.get('side_effect') != definition.side_effect:
                    coverage_errors.append(f"{case['id']}: risk metadata drift for {name}")
    for definition in sorted(host.registry.definitions(), key=lambda item: item.name):
        facing = host._allowed(definition)
        rows.append({'capability': definition.name, 'model_facing': facing,
                     'description': definition.description,
                     'description_words': len(definition.description.split()),
                     'required_scenarios': counts[definition.name],
                     'status': ('not_model_facing' if not facing else
                                'covered' if counts[definition.name] >= 2 else
                                'undercovered')})
    facing_rows = [row for row in rows if row['model_facing']]
    description_warnings = [row['capability'] for row in rows if row['model_facing']
                            and (row['description_words'] < 4 or len(row['description'].strip()) < 20)]
    return {'corpus_sha256': corpus_sha256(cases), 'scenarios': len(cases),
            'registered': len(rows), 'model_facing': len(facing_rows),
            'intentionally_not_model_facing': len(rows) - len(facing_rows),
            'model_facing_with_two_required_scenarios': sum(row['required_scenarios'] >= 2 for row in facing_rows),
            'model_facing_with_one_required_scenario': sum(row['required_scenarios'] == 1 for row in facing_rows),
            'model_facing_with_no_required_scenarios': sum(row['required_scenarios'] == 0 for row in facing_rows),
            'coverage_errors': coverage_errors,
            'description_quality_warnings': description_warnings, 'rows': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=DEFAULT_COVERAGE_CASES)
    parser.add_argument('--json', type=Path, default=Path('evals/llm_tools/results/capability_coverage_audit.json'))
    parser.add_argument('--strict', action='store_true', help='fail when an exposed capability has fewer than two probes or schema/risk metadata drifts')
    args = parser.parse_args(argv)
    host = build_default_host()
    cases = load_scenarios(args.cases)
    report = audit_coverage(host, cases)
    routing = audit_scenarios(host, cases)
    report['routing_failures'] = routing['corpus_failures']
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"LLM capability coverage: {report['registered']} registered; "
          f"{report['model_facing']} model-facing; "
          f"{report['intentionally_not_model_facing']} intentionally unavailable to the model.")
    print(f"Required in >=2 scenarios: {report['model_facing_with_two_required_scenarios']}; "
          f"in 1: {report['model_facing_with_one_required_scenario']}; "
          f"in 0: {report['model_facing_with_no_required_scenarios']}.")
    if report['coverage_errors']:
        print(f"Coverage fixture errors: {len(report['coverage_errors'])}; first: {report['coverage_errors'][0]}")
    if report['description_quality_warnings']:
        print(f"Short or empty model-facing descriptions: {', '.join(report['description_quality_warnings'])}")
    if report['routing_failures']:
        print(f"Coverage routing failures: {len(report['routing_failures'])}; first: {report['routing_failures'][0]['id']}")
    return 2 if args.strict and (report['model_facing_with_one_required_scenario']
                                  or report['model_facing_with_no_required_scenarios']
                                  or report['coverage_errors'] or report['routing_failures']
                                  or report['description_quality_warnings']) else 0


if __name__ == '__main__':
    raise SystemExit(main())

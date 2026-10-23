"""Original metadata-only Campaign 1 audit, with query-only development novelty.

No capability handler, model, provider, account, GUI, terminal, or process action
is invoked. Old final/holdout corpora are excluded by an explicit allowlist.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from hanni.config.loader import load_config
from hanni.evals.isolation import isolated_host
from hanni.mcp.host import McpHost, McpTool, classification
from hanni.tools.base import ToolPermissionError, ToolValidationError
from hanni.tools.registry import build_default_registry
from scripts.campaign1_verification.contract import validate_case
OLD_DEVELOPMENT = ['evals/routing/cases.jsonl', 'evals/routing/voice_routing_v1.jsonl', 'evals/routing/phrase_probe_v2.jsonl', 'evals/routing/multiturn_v1.jsonl', 'evals/routing/language_generalization_v2.jsonl', 'evals/routing/language_generalization_v3.jsonl', 'evals/routing/language_generalization_v4.jsonl', 'evals/routing/language_generalization_v4b.jsonl', 'evals/routing/false_positive_v4.jsonl', 'evals/routing/academic_calendar.jsonl', 'evals/retrieval/development_v2.jsonl']

def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()

def normalized(query):
    return ' '.join(re.findall('\\w+', query.casefold()))

def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf8')

def audit_novelty(cases):
    old = {}
    sources = []
    for relative in OLD_DEVELOPMENT:
        path = ROOT / relative
        if not path.exists():
            continue
        sources.append(relative)
        for line in path.read_text(encoding='utf8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            record = json.loads(line)
            for query in query_fields(record):
                old.setdefault(normalized(query), {'query': query, 'source': relative, 'sha256': sha(normalized(query))})
    exact = []
    near = []
    old_tokens = [(set(query.split()), record) for query, record in old.items()]
    for case in cases:
        for turn, query_text in enumerate(query_fields(case), 1):
            query = normalized(query_text)
            if query in old:
                exact.append({'id': case['id'], 'turn': turn, 'old_query_sha256': old[query]['sha256'], 'source': old[query]['source']})
            tokens = set(query.split())
            for old_set, record in old_tokens:
                overlap = len(tokens & old_set) / max(1, len(tokens | old_set))
                if overlap >= 0.8:
                    near.append({'id': case['id'], 'turn': turn, 'jaccard': overlap, 'development_query': query_text, 'old_query_only': record['query'], 'source': record['source'], 'old_query_sha256': record['sha256']})
    return {'scope': 'only explicitly allowlisted older public DEVELOPMENT query fields; no final corpora or answer fields', 'sources': sources, 'old_unique_queries': len(old), 'new_cases': len(cases), 'exact_duplicates': exact, 'near_duplicate_threshold': 0.8, 'near_duplicates': near}

def query_fields(record):
    """Inspect only query-bearing fields, never history assistant/final answers."""
    seen = set()
    values = [record.get('query')]
    for turn in record.get('turns', []):
        values.append(turn if isinstance(turn, str) else turn.get('query') if isinstance(turn, dict) else None)
    for query in values:
        if isinstance(query, str) and normalized(query) not in seen:
            seen.add(normalized(query))
            yield query

def validate_contracts(host):
    """Original definition validation and denied host admission, no handlers."""
    rows = []
    for definition in host.registry.definitions():
        schema = definition.argument_schema()
        required = {}
        for field in schema.get('required', []):
            spec = schema['properties'][field]
            kinds = spec.get('type')
            kinds = kinds if isinstance(kinds, list) else [kinds]
            value = spec['enum'][0] if spec.get('enum') else False if 'boolean' in kinds else max(spec.get('minimum', 0), 0) if 'integer' in kinds else float(max(spec.get('minimum', 0), 0)) if 'number' in kinds else [] if 'array' in kinds else {} if 'object' in kinds else 'x' * max(spec.get('minLength', 1), 1)
            required[field] = value
        try:
            definition.validate_arguments(required)
            required_valid = True
        except ToolValidationError:
            required_valid = False
        unknown_rejected = False
        wrong_types = []
        try:
            definition.validate_arguments({**required, 'campaign1_unregistered_argument': True})
        except ToolValidationError:
            unknown_rejected = True
        for field in schema['properties']:
            try:
                definition.validate_arguments({**required, field: object()})
            except ToolValidationError:
                wrong_types.append(field)
        allowed = host._allowed(definition)
        denied_prepare = None
        if not allowed:
            tool = McpTool('hanni', definition.name, definition.name.replace('.', '_'), definition.description, schema, classification(definition), definition_hash=definition.external_definition_hash)
            try:
                host.prepare_call(tool, {})
            except ToolPermissionError:
                denied_prepare = True
            except Exception:
                denied_prepare = False
            else:
                denied_prepare = False
        rows.append({'tool': definition.name, 'schema': schema, 'unknown_argument_rejected': unknown_rejected, 'minimal_required_arguments_valid': required_valid, 'wrong_type_fields_rejected': wrong_types, 'field_count': len(schema['properties']), 'owner_menu_allowed': allowed, 'denied_host_preparation_rejected': denied_prepare, 'passed': required_valid and unknown_rejected and (len(wrong_types) == len(schema['properties'])) and (denied_prepare is not False)})
    return {'scope': 'all original contracts; schema validation and host preparation only; no model, handler or provider execution', 'contracts': len(rows), 'passed': sum((row['passed'] for row in rows)), 'results': rows}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--measure', action='store_true')
    args = parser.parse_args()
    destination = args.output.resolve()
    allowed = (ROOT / 'data' / 'campaign1-engineering').resolve()
    if not destination.is_relative_to(allowed) or destination.exists():
        raise SystemExit('Output must be a new ignored engineering directory.')
    destination.mkdir(parents=True)
    corpus = ROOT / 'evals' / 'campaign1' / 'development.jsonl'
    cases = [json.loads(line) for line in corpus.read_text(encoding='utf8').splitlines() if line.strip()]
    config = load_config(ROOT / 'config', data_dir=destination / 'state', env={})
    host = isolated_host(McpHost(build_default_registry(config, data_dir=destination / 'state'), read_only=config.hanni.mcp.read_only, allowed_actions=config.hanni.mcp.allowed_actions, max_tools=config.hanni.mcp.max_tools_per_turn, timezone_name=config.hanni.user.timezone))
    inventory = {definition.name: {'input_schema': definition.argument_schema(), 'output_fields': definition.output_schema, 'permission': definition.permission_level, 'risk': definition.risk_level, 'effect': definition.side_effect, 'menu_allowed': host._allowed(definition)} for definition in host.registry.definitions()}
    dump(destination / 'inventory.json', inventory)
    invalid = []
    for case in cases:
        try:
            validate_case(case, set(inventory))
        except Exception as exc:
            invalid.append({'id': case.get('id'), 'case_contract_error': type(exc).__name__})
        names = [name for group in case['expected']['menu']['essential_groups'] for name in group]
        for name in names + case['fixture']['allowed_actions']:
            if name not in inventory:
                invalid.append({'id': case['id'], 'unknown_tool': name})
        for predicate in case['expected']['arguments']:
            properties = inventory.get(predicate['tool'], {}).get('input_schema', {}).get('properties', {})
            if predicate['field'] not in properties:
                invalid.append({'id': case['id'], 'invalid_argument': predicate})
    novelty = audit_novelty(cases)
    contracts = validate_contracts(host)
    dump(destination / 'all-contract-validation.json', contracts)
    dump(destination / 'novelty-query-only.json', novelty)
    summary = {'scope': 'metadata inventory and authored development contracts; no executions', 'tools': len(inventory), 'cases': len(cases), 'scenario_families': len({c['family'] for c in cases}), 'dispositions': dict(Counter((c['expected']['disposition'] for c in cases))), 'history_cases': sum((bool(c['history']) for c in cases)), 'typed_argument_cases': sum((bool(c['expected']['arguments']) for c in cases)), 'owner_turns': sum((len(c.get('turns') or [c['query']]) for c in cases)), 'required_capability_ids': len({name for c in cases for group in c['expected']['menu']['essential_groups'] for name in group}), 'targeted_capability_ids': len({name for c in cases for name in c['targeted_tools']}), 'unprobed_capability_ids': sorted(set(inventory) - {name for c in cases for name in c['targeted_tools']}), 'all_contract_validation_passed': contracts['passed'], 'production_profile': {'read_only': host.read_only, 'allowed_actions': list(host.allowed_actions), 'max_tools': host.max_tools}, 'invalid_contracts': invalid, 'old_query_exact_duplicates': len(novelty['exact_duplicates']), 'old_query_near_duplicates': len(novelty['near_duplicates']), 'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest()}
    if args.measure:
        results = []
        for case in cases:
            isolated = isolated_host(host, allowed_actions=tuple(case['fixture']['allowed_actions']))
            began = time.perf_counter()
            decision = isolated.route(case['query'], history=case['history'], now=datetime.fromisoformat(case['fixture']['now']))
            selected = [tool.capability_id for tool in decision.tools]
            expected = case['expected']
            menu = all((any((name in selected for name in group)) for group in expected['menu']['essential_groups']))
            safety = not set(selected) & set(expected['forbidden_tools'])
            disposition = expected['disposition']
            disposition_ok = bool(selected) if disposition == 'tool' else not selected and decision.status != 'blocked' if disposition == 'no_tool' else decision.status == 'clarification' and (not selected) if disposition == 'clarify' else decision.status == 'blocked' and (not selected)
            results.append({'id': case['id'], 'family': case['family'], 'selected': selected, 'status': decision.status, 'expected': disposition, 'menu_sufficient': menu, 'safety': safety, 'passed': menu and safety and disposition_ok, 'latency_ms': (time.perf_counter() - began) * 1000, 'fixed_arguments': {tool.capability_id: dict(tool.fixed_arguments) for tool in decision.tools}})
        dump(destination / 'retrieval-results.json', {'scope': 'original metadata-only routing; no model or tool execution', 'corpus_sha256': summary['corpus_sha256'], 'cases': len(results), 'passed': sum((r['passed'] for r in results)), 'results': results})
        summary['retrieval_passes'] = sum((r['passed'] for r in results))
    dump(destination / 'summary.json', summary)
    print(json.dumps(summary))
    return 1 if invalid or novelty['exact_duplicates'] or contracts['passed'] != contracts['contracts'] else 0
if __name__ == '__main__':
    raise SystemExit(main())

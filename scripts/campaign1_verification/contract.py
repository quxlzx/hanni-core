"""Shared declarative case contract; no final queries or answer mappings."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
VERSION = 1
DISPOSITIONS = frozenset({'tool', 'no_tool', 'clarify', 'blocked'})
PREDICATES = frozenset({'eq', 'one_of', 'contains', 'under_fixture', 'nonempty', 'absent'})

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf8')).hexdigest()

def validate_case(case, registered):
    assert isinstance(case, dict) and case['id'] and case['query'].strip()
    assert case['difficulty'] in {'easy', 'medium', 'hard'}
    assert case['scope'] in {'isolated development', 'isolated final'}
    turns = case.get('turns') or [case['query']]
    assert 1 <= len(turns) <= 4 and all((isinstance(q, str) and q.strip() for q in turns))
    expected = case['expected']
    oracles = expected.get('turns') or [expected]
    assert len(oracles) == len(turns)
    for oracle in oracles:
        assert oracle['disposition'] in DISPOSITIONS
        names = oracle.get('required_tools', []) + oracle.get('forbidden_tools', [])
        assert set(names) <= registered
        for group in oracle.get('menu', {}).get('essential_groups', []):
            assert group and set(group) <= registered
        for predicate in oracle.get('arguments', []):
            assert predicate['tool'] in registered and predicate['op'] in PREDICATES
            assert isinstance(predicate['field'], str)
        grounding = oracle.get('grounding', {})
        assert isinstance(grounding, dict)
    assert isinstance(case['fixture'], dict)
    return case

def predicate_passes(value, predicate, *, fixture_root=None):
    field = predicate['field']
    if field == '$path_args':
        from .fixtures import PATH_KEYS, substitute
        if fixture_root is None:
            return False
        paths = [v for k, v in value.items() if k in PATH_KEYS]
        allowed = {Path(substitute(p, fixture_root)).resolve() for p in predicate.get('allowed_paths', [])}
        return bool(paths) and all((isinstance(p, str) and Path(p).resolve().is_relative_to(Path(fixture_root).resolve()) and (not allowed or Path(p).resolve() in allowed) for p in paths))
    missing = object()
    actual = value.get(field, missing)
    wanted = predicate.get('value')
    if fixture_root is not None:
        from .fixtures import substitute
        wanted = substitute(wanted, fixture_root)
    op = predicate['op']
    if op == 'absent':
        return actual is missing
    if actual is missing:
        return False
    if op == 'eq':
        return type(actual) is type(wanted) and actual == wanted
    if op == 'one_of':
        return any((type(actual) is type(v) and actual == v for v in wanted))
    if op == 'contains':
        return isinstance(actual, str) and wanted in actual
    if op == 'nonempty':
        return isinstance(actual, str) and bool(actual.strip())
    if op == 'under_fixture':
        if not isinstance(actual, str) or fixture_root is None:
            return False
        return Path(actual).resolve().is_relative_to(Path(fixture_root).resolve())
    raise ValueError(op)

def menu_metrics(menu, oracle, *, k=8):
    chosen = set(menu[:k])
    groups = oracle.get('menu', {}).get('essential_groups', [])
    hits = sum((bool(chosen.intersection(group)) for group in groups))
    alternatives = oracle.get('menu', {}).get('sufficient_alternatives', [])
    alternative_passes = []
    for alternative in alternatives:
        if isinstance(alternative, dict):
            altgroups = alternative.get('essential_groups', [])
        elif isinstance(alternative, list):
            altgroups = [[v] if isinstance(v, str) else v for v in alternative]
        elif isinstance(alternative, str):
            altgroups = [[alternative]]
        else:
            raise ValueError('Malformed sufficient alternative')
        alternative_passes.append(bool(altgroups) and all((chosen.intersection(g) for g in altgroups)))
    sufficient = (hits == len(groups) if groups else not chosen) or any(alternative_passes)
    return {'k': k, 'essential_groups': len(groups), 'covered_groups': hits, 'recall': hits / len(groups) if groups else None, 'sufficient': sufficient, 'sufficient_alternative_matched': any(alternative_passes), 'unsafe_menu': bool(chosen.intersection(oracle.get('forbidden_tools', [])))}

def acceptable_tools(oracle):
    result = set(oracle.get('required_tools', [])) | set(oracle.get('acceptable_tools', []))
    for group in oracle.get('menu', {}).get('essential_groups', []):
        result.update(group)
    for alternative in oracle.get('menu', {}).get('sufficient_alternatives', []):
        if isinstance(alternative, dict):
            groups = alternative.get('essential_groups', [])
        elif isinstance(alternative, list):
            groups = [[v] if isinstance(v, str) else v for v in alternative]
        elif isinstance(alternative, str):
            groups = [[alternative]]
        else:
            raise ValueError('Malformed sufficient alternative')
        for group in groups:
            result.update(group)
    return result

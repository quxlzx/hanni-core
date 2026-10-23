from hanni.config.schema import parse_hanni, ConfigError
from hanni.core.orchestrator import DEFAULT_SYSTEM_PROMPT, system_prompt_for
from hanni.evals.personality import stratified_cases
from hanni.evals.personality import V2_CASES, PERSONALITY_V2_PROMPT, score_proxy, summarize_pairs
import json

def test_personality_prompt_preserves_base_safety():
    cfg = parse_hanni({'hanni': {'name': 'HANNI'}, 'personality': {'enabled': True, 'style': 'hanni', 'intensity': 0.65}})
    prompt = system_prompt_for(cfg.personality)
    assert prompt.startswith(DEFAULT_SYSTEM_PROMPT)
    assert 'Never invent' in prompt
    assert 'celebrity identity' in prompt
    assert PERSONALITY_V2_PROMPT in prompt

def test_neutral_and_invalid_intensity():
    neutral = parse_hanni({'hanni': {}, 'personality': {'enabled': False}})
    assert system_prompt_for(neutral.personality) == DEFAULT_SYSTEM_PROMPT
    try:
        parse_hanni({'hanni': {}, 'personality': {'intensity': 1.5}})
    except ConfigError:
        pass
    else:
        raise AssertionError('invalid personality intensity was accepted')

def test_personality_ab_samples_each_context():
    cases = [{'family': family, 'id': str(i)} for family in ('conversation', 'diagnostics', 'safety') for i in range(3)]
    selected = stratified_cases(cases, 6)
    assert {case['family'] for case in selected} == {'conversation', 'diagnostics', 'safety'}

def test_v2_pairing_corpus_uses_synthetic_evidence_and_distinct_requests():
    rows = [json.loads(line) for line in V2_CASES.read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 50
    assert len({row['id'] for row in rows}) == 50
    assert len({row['source_case'] for row in rows}) == 50
    assert len({row['family'] for row in rows}) >= 8
    assert all(('evidence' in row and 'query' in row for row in rows))
    assert 'only the supplied evidence' in PERSONALITY_V2_PROMPT

def test_personality_v2_proxy_records_claims_and_unsupported_patterns():
    row = {'claims': [{'pattern': 'cpu'}, {'pattern': 'python'}], 'unsupported_patterns': ['ssd failure']}
    scored = score_proxy('CPU is high; this is not an SSD failure.', {'cpu_percent': 94}, row)
    assert scored['required_claims_matched'] == 1
    assert scored['required_claims_total'] == 2
    assert scored['unsupported_pattern_hits'] == []

def test_personality_summary_keeps_human_judgments_out_of_proxy_scores():
    row = {'claims': [{'pattern': 'cpu'}]}
    pairs = [{'responses': {'baseline': {'proxies': score_proxy('CPU at 94%.', {'cpu_percent': 94}, row), 'latency_ms': 10.0, 'error': None}, 'personality_v2': {'proxies': score_proxy('CPU at 94%, yep.', {'cpu_percent': 94}, row), 'latency_ms': 12.0, 'error': None}}}]
    summary = summarize_pairs(pairs)
    assert summary['personality_v2']['required_claim_completion_proxy_percent'] == 100
    assert 'warmth' not in summary['personality_v2']

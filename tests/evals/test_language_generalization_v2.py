"""Structural language and safety checks outside the development score."""
import json
from pathlib import Path
from hanni.evals.routing import build_default_host
from hanni.evals.routing_multiturn import evaluate
from hanni.tools.language_concepts import conceptual_query, recent_subject
from hanni.tools.routing_intents import clauses

def _names(host, query, history=()):
    return {tool.capability_id for tool in host.route(query, history=history).tools}

def test_corpus_is_distinct_and_balanced():
    rows = [json.loads(line) for line in Path('evals/routing/language_generalization_v2.jsonl').read_text().splitlines()]
    assert len(rows) == 200
    assert len({row['query'].casefold() for row in rows}) == 200
    assert {row['family'] for row in rows} == {'apps', 'diagnostics', 'calendar', 'mixed', 'model', 'files', 'media', 'safety', 'conversation'}
    assert sum((bool(row.get('fixed_arguments')) for row in rows)) >= 10

def test_app_action_concepts_share_existing_tool():
    host = build_default_host()
    for query in ('open Discord', 'fire up discord', 'bring up discord', 'pop open disc'):
        assert 'app.open' in _names(host, query)
    assert 'app.open' not in _names(host, 'what is a disk')

def test_generic_media_is_safe_and_context_bound():
    host = build_default_host()
    assert 'media.play_pause' in _names(host, 'pause my music')
    assert 'spotify.play_pause' in _names(host, 'resume', ({'role': 'user', 'content': 'pause my spotify'},))
    assert host.route('resume').status == 'clarification'
    assert host.route('kill it', history=({'role': 'user', 'content': 'show python processes'},)).status == 'blocked'

def test_compound_segmentation_keeps_resource_lists():
    assert len(clauses("what's my cpu usage and ram usage")) == 1
    assert len(clauses('tmr plans plus ram usage')) == 2
    assert len(clauses('open discord and check cpu')) == 2

def test_recent_subject_uses_only_latest_user_turn():
    assert recent_subject(({'role': 'user', 'content': 'pause spotify'},)) == 'spotify'
    assert recent_subject(({'role': 'user', 'content': 'pause spotify'}, {'role': 'assistant', 'content': 'Paused'}, {'role': 'user', 'content': 'what is mcp'})) is None
    assert 'model status' not in conceptual_query('what do you think about local ai')

def test_multiturn_corpus_has_50_dialogues():
    rows = [json.loads(line) for line in Path('evals/routing/multiturn_v1.jsonl').read_text().splitlines()]
    assert len(rows) == 50
    assert sum((len(row['turns']) for row in rows)) >= 100
    first = evaluate(build_default_host(), rows[:2])
    assert first['dialogues'] == 2
    assert first['turn_success_percent'] == 100

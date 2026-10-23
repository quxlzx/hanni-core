"""Structural retrieval checks with paraphrases outside the V3 development set."""
from datetime import datetime
from hanni.evals.routing import build_default_host
from hanni.tools.intent_prototypes import app_entity, match_intent, rank_intents
from hanni.tools.routing_intents import clauses
NOW = datetime.fromisoformat('2026-09-24T12:00:00-04:00')

def route(query, *, history=()):
    return build_default_host().route(query, history=history, now=NOW)

def names(query, *, history=()):
    return [tool.capability_id for tool in route(query, history=history).tools]

def test_prototype_requires_context_and_never_confuses_disk_with_discord():
    assert app_entity('open disc') == 'Discord'
    assert app_entity('check disk activity') is None
    assert match_intent('disk') is None
    assert names('could you bring disc up') == ['app.open']
    assert 'app.open' not in names('disk is full, open it')

def test_resource_status_and_contributor_are_separate():
    assert names('show total ram percentage')[0] == 'system.stats'
    assert names('which app hogs my memory')[0] == 'process.top_memory'
    assert names('what is chewing cpu cycles')[0] == 'process.top_cpu'
    assert names('copying files makes the machine stutter')[0] == 'process.top_disk_io'
    assert names('can you read CPU temperature')[0] == 'system.stats'

def test_compound_clauses_keep_family_evidence_and_dates():
    assert len(clauses('what is booked friday along with cpu load')) == 2
    assert len(clauses('cpu and ram usage')) == 1
    result = route('what is booked friday along with cpu load')
    selected = {tool.capability_id: tool for tool in result.tools}
    assert {'google_calendar.agenda', 'system.stats'} <= set(selected)
    assert selected['google_calendar.agenda'].fixed_arguments['start_date'] == '2026-09-25'

def test_permissions_followup_and_calendar_create_keep_safety_boundaries():
    assert names('are you permitted to end a process') == ['hanni.permissions']
    assert route('run this powershell command').status == 'blocked'
    assert not names('show python processes, then kill it')
    previous = ({'role': 'user', 'content': 'pause spotify'},)
    assert 'spotify.play_pause' in names('hey hanni, resume?', history=previous)
    created = route('make a calendar event for games saturday at 4 pm')
    assert [tool.capability_id for tool in created.tools] == ['google_calendar.create']
    assert created.tools[0].fixed_arguments['start'] == '2026-09-26T16:00:00-04:00'

def test_soft_prototypes_explain_new_intent_wording_without_launch_false_positives():
    ranked = rank_intents('put Chrome on screen')
    app = next((row for row in ranked if row.name == 'app_open'))
    assert app.eligible and app.score > 0.58
    assert app.matched_anchors < app.total_anchors
    assert names('put Chrome on screen') == ['app.open']
    assert names('spin up Discord for me') == ['app.open']
    assert 'app.open' not in names('Steam has been interesting lately')
    assert 'app.open' not in names('how do I open Discord')

def test_new_diagnostic_and_model_wording_stays_grounded():
    assert names('directory browsing is delayed')[0] == 'process.top_disk_io'
    assert names('portable power reduces performance')[0] == 'power.plans'
    assert names('what context window are you using') == ['model.status']
    assert names('what is video memory') == []

def test_implicit_topic_shift_preserves_both_domains():
    assert clauses('Friday agenda, remaining disk space') == ('Friday agenda', 'remaining disk space')
    assert len(clauses('song status and model context')) == 2
    assert len(clauses('CPU and RAM usage')) == 1
    assert {'google_calendar.agenda', 'disk.free_space'} <= set(names('Friday agenda, remaining disk space'))

def test_general_knowledge_does_not_expose_live_tools():
    for query in ('how does a processor work in general', 'what is a calendar invitation', 'what does a file system do', 'tell me about the history of memory chips', 'what does stop mean in a music score'):
        assert names(query) == []
    assert names('what does the log say at the end') == ['file.tail']

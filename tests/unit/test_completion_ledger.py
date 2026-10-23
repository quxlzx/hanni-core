from hanni.evals.routing import build_default_host
from hanni.mcp.completion import CompletionLedger

def test_mixed_request_tracks_each_clause_separately():
    host = build_default_host()
    query = 'open discord and check cpu'
    ledger = CompletionLedger.from_request(host, query, decision=host.route(query))
    assert len(ledger.subtasks) == 2
    ledger.observe('app.open', {'ok': True, 'data': {'app': 'Discord', 'verified': True}})
    assert len(ledger.pending) == 1
    ledger.observe('system.stats', {'ok': True, 'data': {'cpu_percent': 24}})
    assert not ledger.pending

def test_accepted_app_launch_is_reported_without_claiming_verification():
    host = build_default_host()
    ledger = CompletionLedger.from_request(host, 'open discord', decision=host.route('open discord'))
    ledger.observe('app.open', {'ok': True, 'data': {'app': 'Discord', 'outcome': 'accepted', 'verified': False}})
    assert not ledger.unresolved_actions
    assert ledger.accepted_actions[0].accepted_target == 'Discord'
    assert not ledger.pending
    ledger = CompletionLedger.from_request(host, 'open discord', decision=host.route('open discord'))
    ledger.observe('app.open', {'ok': True, 'data': {'app': 'Discord', 'outcome': 'verified', 'verified': True}})
    assert not ledger.unresolved_actions

def test_launch_is_not_spotify_playback_completion():
    host = build_default_host()
    query = 'play spotify'
    ledger = CompletionLedger.from_request(host, query, decision=host.route(query))
    ledger.observe('spotify.status', {'ok': True, 'data': {'running': False, 'playing': False}})
    ledger.observe('spotify.launch', {'ok': True, 'data': {'started': True, 'running': True}})
    assert ledger.pending
    ledger.observe('spotify.play_pause', {'ok': True, 'data': {'playing': True}})
    assert not ledger.pending

"""Recorded-event delivery/privacy and rate limits without native notifications."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[2]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'desktop' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
desktop = load('desktop_notice_main', 'main.py')
notices = load('desktop_notice_feed', 'notifications.py')

def snapshot(*items, categories=None):
    return {'available': True, 'items': list(items), 'preferences': {'categories': categories or {}}}

def item(identifier, title='Recorded event', **fields):
    return {'id': identifier, 'title': title, 'message': 'Sensitive detail must never reach a native balloon', 'read': False, 'dismissed': False, 'category': 'tools', 'priority': 'informational', **fields}

def test_native_feed_ignores_initial_history_deduplicates_and_respects_read_dismissed_and_category_preferences():
    feed = notices.NotificationFeed()
    assert feed.observe(snapshot(item('old'))) == []
    assert feed.observe(snapshot(item('old'), item('read', read=True), item('dismissed', dismissed=True), item('disabled', category='calendar'), item('new', title='Tool failed'), categories={'calendar': False})) == ['Tool failed']
    assert feed.observe(snapshot(item('new', title='Tool failed'))) == []

def test_native_feed_prioritizes_critical_events_and_only_sends_safe_redacted_titles():
    feed = notices.NotificationFeed()
    feed.observe(snapshot())
    result = feed.observe(snapshot(item('normal', 'Local reminder'), item('critical', '  Model\nfailed\x00 ', priority='critical'), item('action', 'Review required', priority='action_required')))
    assert result == ['Model failed', 'Review required', 'Local reminder']
    assert all(('Sensitive' not in title for title in result))
    assert feed.observe(snapshot(item('long', 'x' * 200))) == ['x' * 120]

def test_native_feed_bounds_memory_and_handles_malformed_snapshot_without_losing_startup_semantics():
    feed = notices.NotificationFeed()
    assert feed.observe({'available': False}) == []
    assert feed.observe({'available': True, 'items': None}) == []
    assert not feed.initialized
    assert feed.observe(snapshot(item('first'))) == []
    assert feed.observe({'available': True, 'items': [None, {'id': []}, item('valid', category=[], priority=[])], 'preferences': []}) == ['Recorded event']
    for offset in range(4):
        feed.observe(snapshot(*(item(f'{offset}-{index}') for index in range(1000))))
    assert len(feed.seen) == len(feed.order) == 2048

def test_native_notification_rate_limit_allows_three_per_minute_and_recovers_at_boundary():
    limit = notices.NotificationRateLimit()
    assert [limit.admit(now) for now in [0, 1, 2, 3, 59]] == [True, True, True, False, False]
    assert limit.admit(60)
    assert not limit.admit(60.5)
    assert limit.admit(61)

def test_native_private_get_sends_ephemeral_authentication_header_without_payload(monkeypatch):
    response = SimpleNamespace(status=200, read=lambda maximum: json.dumps(snapshot()).encode())
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(desktop.http.client, 'HTTPConnection', lambda *args, **kwargs: connection)
    desktop.request_json(desktop.DEFAULT_URL, '/api/notifications', token='ephemeral-token')
    method, path, body, headers = connection.request.call_args.args
    assert method == 'GET' and path == '/api/notifications' and (body is None)
    assert headers['X-Hanni-Token'] == 'ephemeral-token'
    connection.close.assert_called_once()

def test_desktop_delivery_is_opt_in_read_only_and_shares_rate_limit_with_connection_notices(tmp_path):
    request = Mock(side_effect=[{'token': 'ephemeral'}, snapshot(item('old')), {'token': 'ephemeral'}, snapshot(item('new', 'Task due'))])
    session = SimpleNamespace(url=desktop.DEFAULT_URL, request=request)
    app = desktop.DesktopApp(session, tmp_path, 'HANNI OS', desktop.load_preferences(tmp_path / 'window.json'))
    app.tray = SimpleNamespace(HAS_NOTIFICATION=True, notify=Mock())
    app.notification_limit = notices.NotificationRateLimit()
    app.observe_notifications()
    request.assert_not_called()
    app.preferences['notifications'] = True
    app.observe_notifications()
    app.tray.notify.assert_not_called()
    app.observe_notifications()
    app.tray.notify.assert_called_once_with('Task due', 'HANNI OS')
    assert all((call.args[1] in {'/api/chat?before=1', '/api/notifications'} and 'body' not in call.kwargs for call in request.call_args_list))
    assert request.call_args_list[-1].kwargs == {'token': 'ephemeral'}
    app.notify('Connection reconnected')
    app.notify('Model ready')
    app.notify('Flood event')
    assert app.tray.notify.call_count == 3
    app.preferences['notifications'] = False
    app.observe_notifications()
    assert app.notification_feed is None
    assert not (tmp_path / 'window.json').exists()

def test_sparse_real_chat_snapshot_bootstraps_native_token_without_reading_large_or_private_history():
    from hanni.dashboard.chat import ChatHub
    hub = ChatHub()
    try:
        for _ in range(18):
            hub.note('Private owner conversation', 's' * 64000)
        assert len(json.dumps(hub.snapshot()).encode()) > 1048576
        sparse = hub.snapshot(before=1)
        assert sparse['messages'] == [] and len(json.dumps(sparse).encode()) < 512
        assert sparse['token'] == hub.token and sparse['epoch'] == hub.epoch
        assert 'Private owner conversation' not in json.dumps(sparse)
        assert sparse['ready'] == hub.snapshot()['ready']
    finally:
        hub.close()
        hub.db.close()

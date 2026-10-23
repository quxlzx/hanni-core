"""V3.6 actual Google adapters against controlled provider/account dependencies.

All provider-shaped evidence here is MOCK, never live Google authentication/API.
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/v36_engineering'))
from fixtures import GoogleProvider, GoogleVault
from controlled_launcher import EmptyVault
from hanni.config.loader import load_config
from hanni.tools import build_default_registry
from hanni.tools.base import ToolRequest, ToolPermissionError, ToolValidationError
from hanni.tools.google_access import GoogleAccess

@pytest.fixture
def controlled(tmp_path):
    config = load_config(ROOT / 'config', data_dir=tmp_path, env={})
    registry = build_default_registry(config)
    provider = GoogleProvider()
    registry.google_access._vault = GoogleVault()
    registry.google_access.transport = provider
    yield (registry, provider)
    registry.context.reliability.close()

def execute(registry, name, args=None, **kwargs):
    return registry.execute(ToolRequest(name, args or {}, source='v36-google-mock', **kwargs))

def event_args():
    return {'account': 'personal', 'calendar_id': 'primary', 'summary': 'V36 controlled creation', 'all_day': False, 'start': '2026-11-04T09:00:00-05:00', 'end': '2026-11-04T10:00:00-05:00'}

def test_list_calendars_preserves_provider_identity(controlled):
    registry, provider = controlled
    result = execute(registry, 'google_calendar.list', {'account': 'personal'})
    assert result.ok
    assert result.data['calendars'][0]['id'] == 'primary'
    assert provider.calls[-1]['path'] == '/calendar/v3/users/me/calendarList'

def test_read_agenda_normalizes_owner_timezone(controlled):
    registry, provider = controlled
    start = provider.events['event-v36']['start']['dateTime'][:10]
    result = execute(registry, 'google_calendar.agenda', {'account': 'personal', 'start_date': start, 'days': 1})
    assert result.ok and result.data['events'][0]['id'] == 'event-v36'
    assert result.data['events'][0]['start_local'] == provider.events['event-v36']['start']['dateTime']
    assert provider.calls[-1]['params']['timeMin'].startswith(start + 'T00:00:00')

def test_next_event_minutes_are_derived_from_provider_event(controlled):
    registry, provider = controlled
    result = execute(registry, 'google_calendar.next', {'account': 'personal', 'days': 7})
    assert result.ok and result.data['events'][0]['id'] == 'event-v36'
    assert result.data['minutes_until_start'] > 0

def test_create_receipt_then_actual_read_after_write(controlled):
    registry, provider = controlled
    result = execute(registry, 'google_calendar.create', event_args())
    assert result.ok and result.data['outcome'] == 'created_but_not_reverified'
    event_id = result.data['id']
    assert provider.events[event_id]['start']['dateTime'] == event_args()['start']
    readback = execute(registry, 'google.calendar.read', {'account': 'personal', 'id': event_id})
    assert readback.ok and readback.data['events'][0]['summary'] == event_args()['summary']
    assert len([call for call in provider.calls if call['method'] == 'POST']) == 1

def test_missing_authentication_never_calls_provider(controlled):
    registry, provider = controlled
    registry.google_access._vault = EmptyVault()
    result = execute(registry, 'google_calendar.create', event_args())
    assert not result.ok and (not provider.calls)
    assert not result.data.get('created')

def test_read_only_account_scope_prevents_calendar_write(controlled):
    registry, provider = controlled
    registry.google_access._vault = GoogleVault(grants=('calendar.read',))
    result = execute(registry, 'google_calendar.create', event_args())
    assert not result.ok and (not provider.calls)
    assert 'permission' in str(result.error).lower() or 'authorize' in result.message.lower()

def test_invalid_event_dates_reject_before_provider(controlled):
    registry, provider = controlled
    bad = {**event_args(), 'start': '2026-11-04T10:00:00-05:00', 'end': '2026-11-04T09:00:00-05:00'}
    result = execute(registry, 'google_calendar.create', bad)
    assert not result.ok and (not provider.calls)
    assert 'after' in result.message.lower()

def test_dst_conversion_is_based_on_exact_provider_timestamp(controlled):
    registry, provider = controlled
    provider.events['event-v36'].update(start={'dateTime': '2026-11-04T14:00:00+00:00'}, end={'dateTime': '2026-11-04T15:00:00+00:00'})
    result = execute(registry, 'google_calendar.agenda', {'account': 'personal', 'start_date': '2026-11-04', 'days': 1})
    assert result.ok
    assert result.data['events'][0]['start_local'] == '2026-11-04T09:00:00-05:00'

def test_controlled_api_timeout_is_disclosed_without_success(controlled):
    registry, provider = controlled
    provider.fail = 'timeout'
    result = execute(registry, 'google_calendar.create', event_args())
    assert not result.ok and 'timeout' in result.message.lower()
    assert not result.data.get('created') and len(provider.events) == 1

def test_untrusted_profile_is_rejected_before_provider(controlled):
    registry, provider = controlled
    with pytest.raises(ToolPermissionError):
        execute(registry, 'google_calendar.create', event_args(), actor_profile='everyone_else')
    assert not provider.calls

def test_duplicate_attempted_create_is_not_replayed_through_original_mcp(controlled):
    from hanni.mcp.host import McpHost
    from hanni.mcp.session import McpToolSession
    registry, provider = controlled
    host = McpHost(registry, read_only=True, allowed_actions=('google_calendar.create',))
    tool = host._as_tool(registry.get('google_calendar.create'), fixed_arguments=event_args())
    session = McpToolSession(None, None, host)
    provider.fail = 'timeout'
    first = session._call(tool, {})
    provider.fail = None
    second = session._call(tool, {})
    assert not first['ok']
    assert second['error']['code'] == 'DUPLICATE_ATTEMPTED_ACTION'
    assert len(provider.calls) == 1 and len(provider.events) == 1

def test_google_aliases_keep_original_adapter_handlers(controlled):
    registry, provider = controlled
    for name in ('google_calendar.list', 'google.calendar.list_calendars'):
        assert execute(registry, name, {'account': 'personal'}).ok
    for name in ('google_calendar.agenda', 'google.calendar.events'):
        assert execute(registry, name, {'account': 'personal', 'start_date': provider.events['event-v36']['start']['dateTime'][:10]}).ok
    event = provider.events['event-v36']
    assert execute(registry, 'google.calendar.availability', {'account': 'personal', 'start_date': event['start']['dateTime'][:10], 'days': 1, 'availability_start': event['start']['dateTime'][11:16], 'availability_end': event['end']['dateTime'][11:16]}).ok
    for name in ('google_calendar.next', 'google.calendar.next'):
        assert execute(registry, name, {'account': 'personal'}).ok
    for name in ('google_calendar.create', 'google.calendar.create'):
        assert execute(registry, name, event_args()).ok

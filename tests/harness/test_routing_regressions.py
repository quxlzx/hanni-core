"""Existing workplace tools must retain their own source and authorization."""
import pytest

from hanni.evals.routing import build_default_host
from hanni.tools.capabilities import capability_catalog


@pytest.mark.parametrize('query', ['search the public web for battery recycling', 'web search recent battery research'])
def test_explicit_web_research_does_not_read_local_battery_telemetry(query):
    host = build_default_host()
    decision = host.route(query)
    assert decision.tools[0].capability_id == 'web.search'
    assert 'system.battery' not in {t.capability_id for t in decision.tools}


@pytest.mark.parametrize('query', ['capture current screen text', 'read visible desktop text'])
def test_screen_request_is_blocked_by_read_only_mode_instead_of_reading_clipboard(query):
    host = build_default_host()
    decision = host.route(query)
    assert decision.status == 'blocked' and not decision.tools
    assert 'screen.read_text' in decision.blocked_capabilities


@pytest.mark.parametrize('query', ['create a persistent reminder', 'save a one-time reminder'])
def test_persistent_reminder_retains_its_write_confirmation_boundary(query):
    decision = build_default_host().route(query)
    assert decision.status == 'blocked' and not decision.tools
    assert 'reminder.create' in decision.blocked_capabilities


def test_new_existing_tool_namespaces_have_explicit_advisory_metadata():
    from hanni.tools.capability_metadata import NAMESPACE_DOMAIN
    host = build_default_host()
    catalog = {c.name: c for c in capability_catalog(host.registry)}
    for name, domain in [('web.search', 'research'), ('screen.read_text', 'desktop'), ('reminder.create', 'productivity')]:
        cap = catalog[name]
        assert cap.subfamily in NAMESPACE_DOMAIN and cap.family == domain

"""Passive download privacy/bounds/cleanup, without native or network startup."""
import json
from types import SimpleNamespace
import pytest
from scripts.campaign8_native.passive_downloads import DownloadEvents, observe_downloads

def test_private_url_filename_and_unknown_state_are_withheld():
    events = DownloadEvents()
    events.record('Page.downloadWillBegin', {'url': 'https://example.invalid/private?token=example-public-63ca43501dff', 'suggestedFilename': 'private-owner-document.json', 'state': ['arbitrary'], 'guid': 'example-public-63ca43501dff'})
    text = json.dumps(events.report)
    assert 'example-public-63ca43501dff' not in text and 'owner-document' not in text
    assert events.report['events'] == [{'event': 'Page.downloadWillBegin', 'url_class': 'withheld', 'suggested_filename': 'withheld'}]

def test_cancellation_is_observed_without_inferring_file_delivery():
    events = DownloadEvents()
    events.record('Page.downloadProgress', {'state': 'canceled', 'receivedBytes': 0, 'totalBytes': 85})
    assert events.report['events'][0]['state'] == 'canceled'
    assert events.report['policy_overridden'] is False
    assert 'file_delivered' not in events.report and 'no_global_file' not in events.report

@pytest.mark.parametrize('number', [True, float('inf'), 2 ** 2000])
def test_invalid_byte_counts_are_not_serialized(number):
    events = DownloadEvents()
    events.record('Page.downloadProgress', {'receivedBytes': number})
    assert events.report['events'] == [{'event': 'Page.downloadProgress'}]

def test_event_overflow_is_bounded_and_unknown_events_are_ignored():
    events = DownloadEvents(limit=2)
    for _ in range(7):
        events.record('Page.downloadProgress', {'state': 'canceled'})
    events.record('Page.arbitrary', {'private': 'withheld'})
    assert len(events.report['events']) == 2 and events.report['dropped_events'] == 5

def test_observer_detaches_on_fault_and_never_changes_download_behavior():
    handlers, commands, detaches = ({}, [], [])
    cdp = SimpleNamespace(on=lambda key, value: handlers.update({key: value}), send=lambda command: commands.append(command), detach=lambda: detaches.append(True))
    page = SimpleNamespace(context=SimpleNamespace(new_cdp_session=lambda page: cdp))
    session = SimpleNamespace(page=page, report={})
    with pytest.raises(RuntimeError):
        with observe_downloads(session, enabled=True):
            handlers['Page.downloadProgress']({'state': 'canceled'})
            raise RuntimeError('Controlled probe fault')
    assert commands == ['Page.enable'] and detaches == [True]
    assert session.report['passive_download_observation']['detached'] is True

def test_default_disabled_observer_does_not_access_browser_or_change_receipt():
    session = SimpleNamespace(report={})
    with observe_downloads(session) as observer:
        assert observer is None
    assert session.report == {}

"""Native attachment must preserve the original WebView's download policy."""
import inspect
import pytest
from playwright.sync_api import BrowserType
from scripts.campaign8_native.session import connect_native_cdp

class ControlledConnector:

    def __init__(self, *, error=None):
        self.error = error
        self.calls = []
        self.native_download_policy = 'deny'
        self.browser = object()

    def connect_over_cdp(self, endpoint, *, timeout, no_defaults=False):
        self.calls.append({'endpoint': endpoint, 'timeout': timeout, 'no_defaults': no_defaults})
        if not no_defaults:
            self.native_download_policy = 'allowAndName'
        if self.error is not None:
            raise self.error
        return self.browser

def test_attachment_preserves_original_native_download_policy():
    connector = ControlledConnector()
    actual = connect_native_cdp(connector, 'http://127.0.0.1:61234')
    assert actual is connector.browser
    assert connector.native_download_policy == 'deny'
    assert connector.calls == [{'endpoint': 'http://127.0.0.1:61234', 'timeout': 1000, 'no_defaults': True}]

def test_attachment_failure_never_falls_back_to_context_defaults():
    connector = ControlledConnector(error=TimeoutError('controlled attachment unavailable'))
    with pytest.raises(TimeoutError, match='controlled attachment unavailable'):
        connect_native_cdp(connector, 'http://127.0.0.1:61234')
    assert len(connector.calls) == 1
    assert connector.native_download_policy == 'deny'

def test_installed_playwright_supports_native_default_preservation():
    assert 'no_defaults' in inspect.signature(BrowserType.connect_over_cdp).parameters

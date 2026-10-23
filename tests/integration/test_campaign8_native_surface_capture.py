"""Hidden-target capture classification controls, not real native outcomes."""
from scripts.campaign8_native.development import surface_capture

class Session:
    main = 'owned-main'
    mini = 'owned-mini'

    def __init__(self, main_visible, mini_visible):
        self.visible = {self.main: main_visible, self.mini: mini_visible}
        self.calls = []

    def window_state(self, window):
        return {'visible': self.visible[window], 'owned': True}

    def capture(self, identifier, *, mini=False):
        self.calls.append((identifier, mini))
        return {'path': 'controlled.png'}

def test_visible_mini_captures_mini():
    session = Session(True, True)
    result = surface_capture(session, 'pin', mini=True)
    assert result['captured_surface'] == 'mini'
    assert result['target_visible'] is True
    assert session.calls == [('pin', True)]

def test_dismissed_mini_records_hidden_and_captures_visible_main():
    session = Session(True, False)
    result = surface_capture(session, 'dismiss', mini=True)
    assert result['target_visible'] is False
    assert result['captured_surface'] == 'main'
    assert result['native_windows']['mini']['visible'] is False
    assert session.calls == [('dismiss', False)]

def test_two_hidden_windows_never_claim_visible_pixels():
    session = Session(False, False)
    result = surface_capture(session, 'hidden', mini=True)
    assert result['captured'] is False
    assert session.calls == []

"""Disposable restart-state authority, without a native launch."""
import json
import pytest
from scripts.campaign8_native import session

@pytest.mark.parametrize('invalid', ['outside', 'missing_directory', 'missing_preferences'])
def test_restart_state_cannot_select_owner_or_incomplete_state(tmp_path, monkeypatch, invalid):
    monkeypatch.setattr(session, 'ROOT', tmp_path)
    campaign = tmp_path / 'data/campaign8-native'
    campaign.mkdir(parents=True)
    state = campaign / 'owned-state'
    if invalid == 'outside':
        state = tmp_path / 'owner-preferences'
        state.mkdir()
        (state / 'window.json').write_text('{}')
    elif invalid == 'missing_preferences':
        state.mkdir()
    with pytest.raises(ValueError, match='campaign-owned disposable'):
        session.NativeSession(url='http://127.0.0.1:59999', output=campaign / 'fresh-output', state_directory=state)

def test_prospective_restart_state_is_retained_without_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(session, 'ROOT', tmp_path)
    campaign = tmp_path / 'data/campaign8-native'
    state = campaign / 'first/native-state'
    state.mkdir(parents=True)
    preferences = {'width': 880, 'height': 560, 'mini_pinned': True}
    path = state / 'window.json'
    path.write_text(json.dumps(preferences))
    before = path.read_bytes()
    native = session.NativeSession(url='http://127.0.0.1:59999', output=campaign / 'second', state_directory=state)
    assert native.state_directory == state.resolve()
    assert path.read_bytes() == before
    assert native.process is None

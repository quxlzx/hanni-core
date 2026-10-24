import os
from pathlib import Path
import pytest
from hanni_test_guard import install, TestBoundaryBlocked

install()

@pytest.fixture(autouse=True)
def isolated_test_boundaries(tmp_path, monkeypatch):
    monkeypatch.setenv('HANNI_DATA_DIR', str(tmp_path / 'default-data'))
    monkeypatch.setenv('HANNI_MODEL_STATE', str(tmp_path / 'default-state'))
    monkeypatch.setenv('HANNI_CRON_ROOT', str(tmp_path / 'default-state'))
    monkeypatch.setenv('HANNI_BRIDGE_TOKEN_FILE', str(tmp_path / 'default-state/bridge.token'))
    def blocked(*args, **kwargs):
        raise TestBoundaryBlocked('Real credentials, microphone, speakers and screen capture are disabled in offline tests.')
    import keyring
    monkeypatch.setattr(keyring, 'get_password', lambda *a, **k: None)
    for name in ('set_password', 'delete_password'):
        monkeypatch.setattr(keyring, name, blocked)
    try:
        from keyring.backends.Windows import WinVaultKeyring
    except ImportError:
        WinVaultKeyring = None
    if WinVaultKeyring:
        monkeypatch.setattr(WinVaultKeyring, 'get_password', lambda *a, **k: None)
        for name in ('set_password', 'delete_password'):
            monkeypatch.setattr(WinVaultKeyring, name, blocked)
    try:
        import sounddevice
    except (ImportError, OSError):
        sounddevice = None
    if sounddevice:
        for name in ('InputStream', 'OutputStream', 'RawInputStream', 'RawOutputStream', 'play', 'rec', 'playrec'):
            monkeypatch.setattr(sounddevice, name, blocked)
    try:
        from PIL import ImageGrab
    except ImportError:
        ImageGrab = None
    if ImageGrab:
        monkeypatch.setattr(ImageGrab, 'grab', blocked)
        monkeypatch.setattr(ImageGrab, 'grabclipboard', blocked)

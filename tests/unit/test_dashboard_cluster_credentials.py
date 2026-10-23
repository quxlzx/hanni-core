from types import SimpleNamespace
import pytest
from hanni.dashboard import cluster_credentials as credentials
from tests.unit.cluster_fixture import NODES

@pytest.fixture(autouse=True)
def configured_roster(monkeypatch):
    monkeypatch.setattr(credentials, 'load_nodes', lambda data_dir: NODES)

@pytest.fixture
def vault(monkeypatch):
    entries = {}
    backend = SimpleNamespace(get_password=lambda service, key: entries.get((service, key)), set_password=lambda service, key, value: entries.__setitem__((service, key), value))
    monkeypatch.setattr(credentials, '_backend', lambda: backend)
    return entries

def test_vault_credentials_are_scoped_to_data_directory_and_exact_node(vault, tmp_path):
    password = 'example-public-ebf8e286bd49'
    credentials.set_sudo_password(NODES[0], tmp_path, password)
    stored = credentials.get_sudo_password(NODES[0], tmp_path)
    assert stored.reveal() == password and password not in repr(stored)
    assert credentials.get_sudo_password(NODES[1], tmp_path) is None
    assert credentials.get_sudo_password(NODES[0], tmp_path / 'another-session') is None
    assert len(vault) == 1 and (not list(tmp_path.iterdir()))

@pytest.mark.parametrize('value', ['', 'bad\ninput', 'bad\rinput', 'bad\x00input', None])
def test_invalid_password_cannot_be_saved_or_sent_as_multiple_lines(vault, tmp_path, value):
    with pytest.raises(ValueError, match='single line'):
        credentials.set_sudo_password(NODES[0], tmp_path, value)
    assert not vault

def test_maintenance_node_and_unconfigured_session_have_no_credential(vault, tmp_path):
    with pytest.raises(ValueError, match='active roster'):
        credentials.set_sudo_password(NODES[-1], tmp_path, 'unit-only')
    assert credentials.get_sudo_password(NODES[-1], tmp_path) is None
    assert credentials.get_sudo_password(NODES[0], None) is None
    assert not vault

def test_vault_failure_never_falls_back_to_plaintext_or_exposes_details(monkeypatch, tmp_path):
    password = 'example-public-7c563d37863d'

    def unavailable():
        raise RuntimeError(password)
    monkeypatch.setattr(credentials, '_backend', unavailable)
    assert credentials.get_sudo_password(NODES[0], tmp_path) is None
    with pytest.raises(RuntimeError) as error:
        credentials.set_sudo_password(NODES[0], tmp_path, password)
    assert password not in str(error.value)
    assert not list(tmp_path.iterdir())

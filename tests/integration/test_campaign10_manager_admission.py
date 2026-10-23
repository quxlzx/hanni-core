"""Fresh process binding independently of historical Windows PIDs."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from scripts.campaign10_manager.admission import original_model_admission
from scripts.campaign8_ui.streaming import StreamingAdmissionError
from scripts.campaign10_manager.model import ModelBudget, AdmissionError

@pytest.mark.parametrize('fault', ['none', 'nonloopback', 'wrong_file', 'wrong_alias', 'busy', 'identity_changed', 'low_ram'])
def test_fresh_identity_admission(tmp_path, fault):
    model = tmp_path / 'configured.gguf'
    model.write_bytes(b'Synthetic identity fixture, not weights')
    pid = 45678
    process = SimpleNamespace(pid=pid, is_running=lambda: True, name=lambda: 'llama-server.exe', create_time=lambda: 12345.0, cmdline=lambda: ['llama-server.exe', '-m', str(model)])
    listener = SimpleNamespace(status='LISTEN', laddr=SimpleNamespace(port=8080, ip='0.0.0.0' if fault == 'nonloopback' else '127.0.0.1'), pid=pid)
    spec = SimpleNamespace(endpoint='http://127.0.0.1:8080/v1', model_file='configured.gguf', api_model='supervisor')
    config = SimpleNamespace(models=SimpleNamespace(supervisor=spec))
    props = {'model_path': str(tmp_path / 'other.gguf') if fault == 'wrong_file' else str(model), 'model_alias': 'other' if fault == 'wrong_alias' else 'supervisor', 'total_slots': 1}
    metadata = {'/health': {'status': 'ok'}, '/props': props, '/slots': [{'id': 0, 'is_processing': fault == 'busy'}]}
    memory = SimpleNamespace(available=1024 if fault == 'low_ram' else 8 * 1024 ** 3, percent=50.0)
    expected = {'pid': 111} if fault == 'identity_changed' else None
    with patch('scripts.campaign10_manager.admission.load_config', return_value=config), patch('scripts.campaign10_manager.admission.psutil.virtual_memory', return_value=memory), patch('scripts.campaign10_manager.admission.psutil.net_connections', return_value=[listener]), patch('scripts.campaign10_manager.admission.psutil.Process', return_value=process), patch('scripts.campaign10_manager.admission._metadata', side_effect=lambda path: metadata[path]):
        if fault == 'none':
            value = original_model_admission()
            assert value['process']['pid'] == pid
            assert original_model_admission(value['process'])['process'] == value['process']
        else:
            with pytest.raises(StreamingAdmissionError):
                original_model_admission(expected)

def test_deferred_startup_never_grants_generation(tmp_path):
    budget = ModelBudget(tmp_path / 'owned', maximum=1)
    with pytest.raises(AdmissionError):
        with budget.transport(starting_owned_model=True):
            pass
    assert not budget.wire

from types import SimpleNamespace
from hanni.tools import overview, power
from hanni.tools import diagnostics
from hanni.config.loader import load_config
from pathlib import Path

def test_performance_scope_does_not_call_unmeasured_disk_or_gpu_healthy(monkeypatch):
    monkeypatch.setattr(overview.psutil, 'cpu_percent', lambda interval: 18)
    monkeypatch.setattr(overview.psutil, 'virtual_memory', lambda: SimpleNamespace(percent=54, used=16 * 1024 ** 3, total=32 * 1024 ** 3))
    monkeypatch.setattr(overview.psutil, 'sensors_battery', lambda: None)
    monkeypatch.setattr(overview.psutil, 'boot_time', lambda: 1)
    monkeypatch.setattr(overview.psutil, 'disk_partitions', lambda all: [])
    monkeypatch.setattr(overview.psutil, 'process_iter', lambda attrs: [])
    result = overview._performance({}, None, None)
    assert result.data['healthy'] is True
    assert result.data['cpu_pressure'] == 'normal'
    assert result.data['memory_pressure'] == 'normal'
    assert 'excludes disk I/O' in result.data['snapshot_scope']
    assert 'Disk I/O' in result.message

def test_builtin_power_saver_is_possible_limit_not_proven_cause(monkeypatch):
    text = 'Power Scheme GUID: a1841308-3541-4fab-bc81-f71556f20b4a  (Power saver) *'
    monkeypatch.setattr(power, 'run_powershell', lambda *args, **kwargs: text)
    result = power._plans({}, None, None)
    assert result.data['active_plan_intent'] == 'energy_saving'
    assert result.data['performance_limit_possible'] is True
    assert result.data['causal_status'] == 'possible_not_verified'
    assert 'does not prove' in result.message

def test_model_gpu_placement_requires_owned_process_and_verified_offload(tmp_path, monkeypatch):
    config = load_config(Path('config'), data_dir=tmp_path, env={})
    spec = config.models.supervisor
    import hanni.models.manager as manager_module
    import hanni.models.runtime as runtime_module
    monkeypatch.setattr(manager_module, 'current', lambda _spec: None)
    assert not diagnostics._owned_model_placement(config, spec)['placement_verified']
    log = tmp_path / 'dashboard-supervisor.log'
    log.write_text('offloaded 36/36 layers to GPU\n', encoding='utf-8')
    entry = SimpleNamespace(process=SimpleNamespace(poll=lambda: None), state='READY', command=['llama-server', '--device', 'Vulkan3', '-ngl', '99'])
    monkeypatch.setattr(manager_module, 'current', lambda _spec: SimpleNamespace(entries={spec.id: entry}))
    monkeypatch.setattr(runtime_module, 'gpu_inventory', lambda: [SimpleNamespace(id='Vulkan3', name='Discrete GPU')])
    monkeypatch.setattr(runtime_module, 'load_gpu_routing', lambda _path: {'mode': 'auto'})
    state = diagnostics._owned_model_placement(config, spec)
    assert state['placement_verified'] is True
    assert state['selected_device_name'] == 'Discrete GPU'
    assert state['offloaded_layers'] == 36
    log.write_text('model started without offload evidence\n', encoding='utf-8')
    assert not diagnostics._owned_model_placement(config, spec)['placement_verified']

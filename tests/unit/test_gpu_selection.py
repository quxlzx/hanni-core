from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from hanni.config.loader import load_config
from hanni.config.schema import ConfigError, parse_models
from hanni.models import runtime
from hanni.dashboard import launcher
DEVICES = [('Vulkan9', 'AMD Radeon(TM) Graphics (32000 MiB, 31000 MiB free)'), ('Vulkan4', 'Discrete Small (8192 MiB, 7500 MiB free)'), ('Vulkan7', 'Discrete Large (24576 MiB, 23000 MiB free)'), ('Vulkan2', 'Discrete Medium (16384 MiB, 15000 MiB free)')]

@pytest.fixture
def config(tmp_path):
    config = load_config(data_dir=tmp_path, env={})
    spec = replace(config.models.supervisor, vision_projector=None)
    return replace(config, models=replace(config.models, models=(spec,)))

def test_auto_routes_single_assistant_to_smallest_8gb_class_gpu(config):
    with patch.object(runtime, 'list_devices', return_value=DEVICES):
        assert runtime.resolve_devices(config.models.supervisor) == (['Vulkan4'], 99)
        assert [d.total_mb for d in runtime.gpu_inventory()] == [24576, 16384, 8192]

def test_busy_smallest_fitting_gpu_uses_next_larger_card(config):
    listing = [(k, v.replace('7500 MiB free', '1000 MiB free')) for k, v in DEVICES]
    with patch.object(runtime, 'list_devices', return_value=listing):
        assert runtime.resolve_devices(config.models.supervisor)[0] == ['Vulkan2']

def test_single_gpu_requires_enough_free_budget(config):
    with patch.object(runtime, 'list_devices', return_value=[DEVICES[3]]):
        assert runtime.resolve_devices(config.models.supervisor)[0] == ['Vulkan2']
    low_free = [('Vulkan2', 'Discrete Medium (16384 MiB, 5000 MiB free)')]
    with patch.object(runtime, 'list_devices', return_value=low_free):
        with pytest.raises(RuntimeError, match='insufficient free VRAM'):
            runtime.resolve_devices(config.models.supervisor)

@pytest.mark.parametrize('listing', [[], [('Vulkan0', 'Unknown GPU')], [DEVICES[0]], [('Vulkan0', 'Discrete (16000 MiB, 17000 MiB free)')], [('Vulkan0', 'Intel UHD Graphics (16000 MiB, 15000 MiB free)')]])
def test_unknown_or_shared_memory_does_not_silently_use_default(config, listing):
    with patch.object(runtime, 'list_devices', return_value=listing):
        with pytest.raises(RuntimeError, match='no discrete'):
            runtime.resolve_devices(config.models.supervisor)

def test_failed_discovery_not_treated_as_empty_success():
    with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='backend failure')):
        with pytest.raises(RuntimeError, match='GPU discovery failed'):
            runtime.list_devices(['llama-server'])

def test_command_pins_smallest_eligible_device_and_enables_allocation_evidence(config):
    with patch.object(runtime, 'executable_prefix', return_value=['llama-server']), patch.object(runtime, 'supported_options', return_value='--log-verbosity'), patch.object(runtime, 'list_devices', return_value=DEVICES):
        command = runtime.model_command(config.models.supervisor)
    assert command[command.index('--device') + 1] == 'Vulkan4'
    assert command[command.index('--split-mode') + 1] == 'none'
    assert command[command.index('--main-gpu') + 1] == '0'
    assert command[command.index('--log-verbosity') + 1] == '4'
    assert '--verbose' not in command and '--log-prompts-dir' not in command

def test_manual_mapping_and_cpu_are_preserved(config):
    spec = replace(config.models.supervisor, gpu_selection='configured', device_name_hints=('Discrete Small',))
    with patch.object(runtime, 'list_devices', return_value=DEVICES):
        assert runtime.resolve_devices(spec)[0] == ['Vulkan4']
    with patch.object(runtime, 'list_devices', side_effect=AssertionError('CPU must not probe GPU')):
        assert runtime.resolve_devices(replace(spec, gpu_layers=0)) == ([], 0)

def test_auto_and_manual_options_cannot_conflict():
    row = dict(id='main', role='supervisor', backend='llama.cpp', model_file='test.gguf', endpoint='http://localhost:8080/v1', gpu_selection='smallest_8gb', device_name_hints=['test'])
    with pytest.raises(ConfigError, match='remove manual'):
        parse_models({'models': [row]})

@pytest.mark.parametrize('offload,success', [('offloaded 41/41 layers to GPU', True), ('offloaded 0/41 layers to GPU', False), ('', False)])
def test_launcher_verifies_gpu_offload_and_uses_exact_resolved_command(config, offload, success):
    process = Mock()
    process.poll.return_value = None
    command = ['llama-server', '--device', 'Vulkan7', '-ngl', '99']

    def spawn(cmd, **kwargs):
        assert cmd is command
        kwargs['stdout'].write(offload + '\n')
        kwargs['stdout'].flush()
        return process
    with patch.object(launcher.socket, 'create_connection', side_effect=OSError), patch.object(launcher.subprocess, 'Popen', side_effect=spawn), patch.object(launcher, 'model_command', side_effect=AssertionError('must not reselect')), patch.object(launcher, 'create_client') as client:
        client.return_value.health.return_value = SimpleNamespace(ok=True)
        if success:
            assert launcher.start_model(config, command=command) is process
            process.terminate.assert_not_called()
        else:
            with pytest.raises(RuntimeError, match='offload could not be verified'):
                launcher.start_model(config, command=command)
            process.terminate.assert_called_once()

def test_auto_treats_driver_reported_8176_mib_as_8gb_class(config):
    listing = [('Vulkan0', 'Almost Eight (8176 MiB, 7600 MiB free)'), ('Vulkan1', 'Six Gig (6144 MiB, 6000 MiB free)'), ('Vulkan2', 'Twelve Gig (12288 MiB, 12000 MiB free)')]
    with patch.object(runtime, 'list_devices', return_value=listing):
        assert runtime.resolve_devices(config.models.supervisor)[0] == ['Vulkan0']

def test_dashboard_override_survives_device_reordering_by_name(tmp_path, config):
    path = tmp_path / 'gpu-routing.json'
    spec = config.models.supervisor
    with patch.object(runtime, 'list_devices', return_value=DEVICES):
        selected = next((d for d in runtime.gpu_inventory() if d.id == 'Vulkan2'))
        runtime.save_gpu_routing(path, mode='manual', device=selected)
    reordered = [('Vulkan1', 'Discrete Medium (16384 MiB, 15000 MiB free)'), ('Vulkan8', 'Discrete Small (8192 MiB, 7500 MiB free)'), ('Vulkan3', 'Discrete Large (24576 MiB, 23000 MiB free)')]
    with patch.object(runtime, 'list_devices', return_value=reordered):
        assert runtime.resolve_devices(spec, routing_path=path)[0] == ['Vulkan1']
        state = runtime.gpu_routing_state(spec, routing_path=path)
    assert state['mode'] == 'manual' and state['selected_device_name'] == 'Discrete Medium'

def test_auto_override_restores_smallest_gpu_policy(tmp_path, config):
    path = tmp_path / 'gpu-routing.json'
    spec = config.models.supervisor
    with patch.object(runtime, 'list_devices', return_value=DEVICES):
        medium = next((d for d in runtime.gpu_inventory() if d.id == 'Vulkan2'))
        runtime.save_gpu_routing(path, mode='manual', device=medium)
        assert runtime.resolve_devices(spec, routing_path=path)[0] == ['Vulkan2']
        runtime.save_gpu_routing(path, mode='auto')
        assert runtime.resolve_devices(spec, routing_path=path)[0] == ['Vulkan4']

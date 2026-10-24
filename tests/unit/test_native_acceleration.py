"""Native startup uses real backend discovery and enforces Q8 in both modes."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hanni.native import acceleration
from hanni.native.probe import Facts
from tests.test_stick import firstboot

HELP = '''--cache-type-k --cache-type-v --flash-attn --no-op-offload --log-verbosity
--gpu-layers N max number of layers, 'auto', or 'all'
--fit [on|off] --fit-ctx N
'''
GPU = ('Vulkan0', 'AMD Radeon RX 7900 XT (20464 MiB, 19000 MiB free)')
IGPU = ('Vulkan1', 'AMD Radeon(TM) Graphics (32000 MiB, 31000 MiB free)')


@pytest.mark.parametrize('found,device', [([GPU, IGPU], 'Vulkan0'), ([IGPU], 'Vulkan1'), ([], 'none')])
def test_gpu_preference_and_cpu_fallback_always_keep_q8(found, device):
    with patch.object(acceleration, 'devices', return_value=found), patch.object(acceleration, 'supported_options', return_value=HELP):
        flags = acceleration.flags(Path('/binary'), context=262144)
    assert flags[flags.index('--device') + 1] == device
    assert flags[flags.index('-ctk') + 1] == flags[flags.index('-ctv') + 1] == 'q8_0'
    assert flags[flags.index('-fa') + 1] == 'on'
    if found:
        assert flags[flags.index('-ngl') + 1] == 'auto'
        assert flags[flags.index('--fit-ctx') + 1] == '262144'
    else:
        assert flags[flags.index('-ngl') + 1] == '0'
        assert '--no-op-offload' in flags


def test_software_renderer_is_not_a_gpu():
    with patch.object(acceleration, 'list_devices', return_value=[('Vulkan0', 'llvmpipe'), GPU]):
        assert acceleration.devices(Path('/binary')) == [GPU]


def test_older_server_keeps_explicit_offload_but_never_downgrades_cache():
    with patch.object(acceleration, 'devices', return_value=[GPU]), patch.object(acceleration, 'supported_options', return_value='--cache-type-k --cache-type-v --flash-attn'):
        flags = acceleration.flags(Path('/binary'))
    assert flags[flags.index('-ngl') + 1] == '99'
    assert '-ctk' in flags and '-ctv' in flags


def test_missing_cache_options_fail_clearly():
    with patch.object(acceleration, 'supported_options', return_value='--gpu-layers N'):
        with pytest.raises(RuntimeError, match='cannot enforce Q8'):
            acceleration.flags(Path('/binary'))


@pytest.mark.parametrize('benchmark', [False, True])
def test_discovery_failure_is_not_silently_misreported_as_cpu(benchmark):
    with patch.object(acceleration, 'supported_options', return_value=HELP), patch.object(acceleration, 'devices', side_effect=RuntimeError('driver failure')):
        with pytest.raises(RuntimeError, match='driver failure'):
            acceleration.flags(Path('/binary'), benchmark=benchmark)


def binaries(tmp_path, monkeypatch):
    monkeypatch.setattr(firstboot, 'STICK', tmp_path)
    for name in ('windows-vulkan', 'windows-x86_64', 'linux-vulkan', 'linux-x86_64'):
        directory = tmp_path / 'binaries' / name
        directory.mkdir(parents=True)
        for exe in ('llama-bench', 'llama-server'):
            (directory / exe).touch()


@pytest.mark.parametrize('gpu', [True, False])
def test_binary_selection_uses_detected_backend_devices(tmp_path, monkeypatch, gpu):
    binaries(tmp_path, monkeypatch)
    with patch.object(firstboot.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
            patch.object(acceleration, 'devices', side_effect=lambda directory: [GPU] if gpu and directory.name.endswith('vulkan') else []):
        selected = firstboot.pick_binary(Facts(gpus=[]))
    assert selected.name.endswith('vulkan' if gpu else 'x86_64')


def test_failed_gpu_discovery_uses_installed_cpu_binary(tmp_path, monkeypatch):
    binaries(tmp_path, monkeypatch)
    def discover(directory):
        if directory.name.endswith('vulkan'):
            raise RuntimeError('driver failure')
        return []
    with patch.object(firstboot.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
            patch.object(acceleration, 'devices', side_effect=discover):
        assert firstboot.pick_binary(Facts()).name.endswith('x86_64')


def test_slow_cpu_still_selects_a_model_without_requiring_a_speed_floor(tmp_path, monkeypatch):
    binaries(tmp_path, monkeypatch)
    (tmp_path / 'models').mkdir()
    for model in firstboot.MODEL_FOR_TIER.values():
        (tmp_path / 'models' / model).touch()
    with patch.object(firstboot, 'probe', return_value=Facts(ram_gb=32)), \
            patch.object(firstboot, 'pick_binary', return_value=tmp_path / 'binaries/linux-x86_64'), \
            patch.object(firstboot, 'micro_bench', side_effect=[1.0, 2.0, 4.0]):
        assert firstboot.main([]) == 0
    import yaml
    config = yaml.safe_load((tmp_path / 'state/models.native.yaml').read_text())['models'][0]
    assert Path(config['model_file']).name == firstboot.MODEL_FOR_TIER['pocket']
    assert config['kv_key_type'] == config['kv_value_type'] == 'q8_0'

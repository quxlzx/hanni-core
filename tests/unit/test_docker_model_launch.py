"""Launch-contract regressions; actual GPU evidence is in live receipts."""
import importlib.util
from pathlib import Path
import pytest

def migration():
    path = Path(__file__).resolve().parents[2] / 'deployment/docker-models/hanni_migrate.py'
    spec = importlib.util.spec_from_file_location('hanni_docker_migration_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def value(model='nex'):
    return {'model': model, 'uid': 1000, 'gid': 1000, 'env': {'CUDA_VISIBLE_DEVICES': 'GPU-authorized'}, 'argv': ['/approved/build/bin/llama-server', '-m', '/approved/model.gguf', '--alias', 'approved', '--host', '127.0.0.1', '--port', '8102', '-dev', 'Vulkan1' if model == 'swift' else 'CUDA0']}

def test_launch_pins_daemon_despite_inherited_podman_configuration(monkeypatch):
    module = migration()
    monkeypatch.setenv('DOCKER_HOST', 'unix:///unavailable/podman.sock')
    args = module.docker_args(value())
    assert args[:3] == ['docker', '--host', 'unix:///var/run/docker.sock']
    assert '--read-only' in args and '--cap-drop=ALL' in args and ('--privileged' not in args)
    assert args[args.index('--user') + 1] == '1000:1000'
    assert args[args.index('--network') + 1] == 'host'
    assert '--restart' not in args

def test_swift_never_uses_unverified_original_index_inside_container():
    module = migration()
    snapshot = value('swift')
    with pytest.raises(ValueError, match='not verified'):
        module.docker_args(snapshot)
    snapshot['container_device'] = 'Vulkan0'
    args = module.docker_args(snapshot)
    image = args.index(module.IMAGE)
    assert args[image + 1:][args[image + 1:].index('-dev') + 1] == 'Vulkan0'
    assert snapshot['argv'][-1] == 'Vulkan1'

def test_probe_cannot_load_weights_or_open_a_model_listener():
    module = migration()
    args = module.docker_args(value(), probe=True)
    assert args[args.index('--network') + 1] == 'none'
    assert args[-2:] == ['/approved/build/bin/llama-server', '--list-devices']
    assert '-m' not in args and '--port' not in args

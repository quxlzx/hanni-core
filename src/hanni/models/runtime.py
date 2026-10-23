"""One version-aware llama.cpp command builder for every local launcher."""
from functools import lru_cache
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

# Windows/driver APIs commonly report an 8 GiB card slightly below 8192 MiB.
# Treat 7.5 GiB or more as an 8 GB-class adapter for automatic HANNI routing.
AUTO_GPU_MIN_MB = 7680
GPU_ROUTING_FILENAME = 'gpu-routing.json'


def executable_prefix():
    for name, suffix in [('llama-server', []), ('llama', ['serve'])]:
        executable = shutil.which(name)
        if executable:
            return [executable, *suffix]
    cache = Path(os.getenv('LOCALAPPDATA', ''))/'Microsoft/WinGet/Packages/ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe'
    for name, suffix in [('llama-server.exe', []), ('llama.exe', ['serve'])]:
        if (cache/name).is_file(): return [str(cache/name), *suffix]
    raise RuntimeError('llama.cpp is missing. Install ggml.llamacpp or add llama-server to PATH.')


@lru_cache(maxsize=8)
def inspect_help(prefix, version_stamp):
    result = subprocess.run([*prefix, '--help'], capture_output=True, text=True, timeout=15,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.stdout + '\n' + result.stderr


def supported_options(prefix):
    path = Path(prefix[0])
    return inspect_help(tuple(prefix), path.stat().st_mtime_ns if path.is_file() else 0)


def list_devices(prefix=None):
    prefix = prefix or executable_prefix()
    probe = prefix[:1] + (['cli'] if len(prefix) > 1 else [])
    result = subprocess.run([*probe, '--list-devices'], capture_output=True, text=True, timeout=10,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('llama.cpp GPU discovery failed: ' + (result.stderr or result.stdout)[-500:])
    return re.findall(r'^\s*([A-Za-z][\w-]*\d+):\s*(.+)$', result.stdout+'\n'+result.stderr, re.M)


@dataclass(frozen=True)
class DeviceMemory:
    id: str
    name: str
    total_mb: int
    free_mb: int


def gpu_inventory(prefix=None):
    """Use the serving binary's device IDs and memory, not Windows AdapterRAM."""
    devices = []
    for key, description in list_devices(prefix):
        memory = re.fullmatch(r'(.*?)\s*\((\d+) MiB, (\d+) MiB free\)\s*', description)
        if not memory:
            continue  # Unknown capacity is not usable VRAM.
        name, total, free = memory.groups()
        # Known UMA/software adapters can advertise shared host RAM as GPU memory.
        # Manual device_name_hints remain available for unusual hardware.
        if re.search(r'llvmpipe|lavapipe|software|Microsoft Basic|\bintegrated\b|\bAPU\b|'
                     r'Radeon\s*(?:\(TM\)\s*)?Graphics\b|Radeon\s+\d{3,4}M\b|'
                     r'Intel.*(?:\bUHD\b|\bHD\b|\bIris\b)|Intel\s*(?:\(R\)\s*)?Graphics\b', name, re.I):
            continue
        if int(total) <= 0 or not 0 <= int(free) <= int(total):
            continue
        devices.append(DeviceMemory(key, name.strip(), int(total), int(free)))
    return sorted(devices, key=lambda d: (-d.total_mb, -d.free_mb, d.id))


def gpu_routing_path(data_dir):
    return Path(data_dir) / GPU_ROUTING_FILENAME


def load_gpu_routing(path=None):
    """Load the owner's GPU override. Invalid/missing state safely falls back to AUTO."""
    if path is None:
        return {'mode': 'auto'}
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'mode': 'auto'}
    except (OSError, ValueError, TypeError) as exc:
        log.warning('Ignoring invalid GPU routing state %s: %s', path, exc)
        return {'mode': 'auto'}
    if not isinstance(data, dict) or data.get('mode') not in {'auto', 'manual'}:
        return {'mode': 'auto'}
    if data['mode'] == 'auto':
        return {'mode': 'auto'}
    name = data.get('device_name')
    device_id = data.get('device_id')
    total_mb = data.get('total_mb')
    if not isinstance(name, str) or not name.strip() or not isinstance(device_id, str):
        return {'mode': 'auto'}
    return {'mode': 'manual', 'device_name': name.strip(), 'device_id': device_id,
            'total_mb': total_mb if isinstance(total_mb, int) and total_mb > 0 else None}


def save_gpu_routing(path, *, mode, device=None):
    """Persist AUTO or a validated manual adapter choice atomically."""
    if mode not in {'auto', 'manual'}:
        raise ValueError('GPU routing mode must be auto or manual')
    payload = {'mode': mode}
    if mode == 'manual':
        if device is None:
            raise ValueError('Manual GPU routing requires a device')
        payload.update(device_id=device.id, device_name=device.name, total_mb=device.total_mb)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return payload


def _fits(device, spec, reserve_mb):
    return device.free_mb >= spec.vram_budget_mb + reserve_mb


def _manual_gpu(devices, settings):
    # Device IDs are useful within one boot, but names survive normal Vulkan/CUDA
    # re-enumeration. Prefer an exact ID+name match, then fall back to name/capacity.
    exact = [d for d in devices if d.id == settings.get('device_id') and
             d.name.casefold() == settings.get('device_name', '').casefold()]
    if exact:
        return exact[0]
    named = [d for d in devices if d.name.casefold() == settings.get('device_name', '').casefold()]
    total = settings.get('total_mb')
    if total:
        capacity = [d for d in named if abs(d.total_mb-total) <= 256]
        if capacity:
            named = capacity
    return named[0] if named else None


def select_gpu(spec, prefix=None, *, reserve_mb=1024, routing_path=None):
    devices = gpu_inventory(prefix)
    if not devices:
        raise RuntimeError(f'{spec.id}: no discrete llama.cpp GPU with known VRAM; check --list-devices or configure explicit device_name_hints')

    settings = load_gpu_routing(routing_path)
    if settings['mode'] == 'manual':
        selected = _manual_gpu(devices, settings)
        if selected is None:
            raise RuntimeError(f"{spec.id}: selected GPU '{settings.get('device_name')}' is not available; choose AUTO or another GPU in the dashboard")
        if not _fits(selected, spec, reserve_mb):
            raise RuntimeError(f'{spec.id}: selected GPU {selected.name} has {selected.free_mb} MiB free, but '
                               f'{spec.vram_budget_mb + reserve_mb} MiB is required')
        return selected

    if spec.gpu_selection == 'smallest_8gb':
        # Smallest qualifying discrete card first. This keeps larger GPUs free for
        # heavier workloads while making the rule independent of adapter numbering.
        order = sorted((d for d in devices if d.total_mb >= AUTO_GPU_MIN_MB),
                       key=lambda d: (d.total_mb, -d.free_mb, d.name.casefold(), d.id))
        if not order:
            raise RuntimeError(f'{spec.id}: no discrete 8 GB-class GPU found (minimum {AUTO_GPU_MIN_MB} MiB reported VRAM)')
    else:
        # Legacy most_vram behavior remains available for old profiles/tests.
        preferred = devices[spec.gpu_preference] if spec.gpu_preference < len(devices) else devices[0]
        order = [preferred] + [device for device in devices if device.id != preferred.id]

    for device in order:
        if _fits(device, spec, reserve_mb):
            log.info('%s GPU: %s (%s), %s MiB VRAM, %s MiB free; budget %s + reserve %s MiB',
                     spec.id, device.name, device.id, device.total_mb, device.free_mb, spec.vram_budget_mb, reserve_mb)
            return device
    raise RuntimeError(f'{spec.id}: insufficient free VRAM on eligible GPUs for '
                       f'{spec.vram_budget_mb} MiB budget + {reserve_mb} MiB reserve')


def gpu_routing_state(spec, prefix=None, *, reserve_mb=1024, routing_path=None):
    devices = gpu_inventory(prefix)
    settings = load_gpu_routing(routing_path)
    selected = None
    error = None
    try:
        if spec.gpu_layers:
            selected = select_gpu(spec, prefix, reserve_mb=reserve_mb, routing_path=routing_path)
    except RuntimeError as exc:
        error = str(exc)
    return {
        'mode': settings['mode'],
        'requested_device_id': settings.get('device_id'),
        'requested_device_name': settings.get('device_name'),
        'selected_device_id': None if selected is None else selected.id,
        'selected_device_name': None if selected is None else selected.name,
        'minimum_auto_vram_mb': AUTO_GPU_MIN_MB,
        'error': error,
        'devices': [
            {'id': d.id, 'name': d.name, 'total_mb': d.total_mb, 'free_mb': d.free_mb,
             'auto_eligible': d.total_mb >= AUTO_GPU_MIN_MB}
            for d in sorted(devices, key=lambda d: (d.total_mb, d.name.casefold(), d.id))
        ],
    }


def resolve_devices(spec, prefix=None, *, reserve_mb=1024, routing_path=None):
    if not spec.gpu_layers:
        return [], 0
    if spec.gpu_selection in {'most_vram', 'smallest_8gb'}:
        return [select_gpu(spec, prefix, reserve_mb=reserve_mb, routing_path=routing_path).id], spec.gpu_layers
    if not spec.device_name_hints:
        return [], spec.gpu_layers
    available = list_devices(prefix)
    def match(hints):
        resolved = []
        for hint in hints:
            matches = [key for key, text in available if hint.casefold() in text.casefold()]
            if len(matches) != 1:
                return None
            resolved.append(matches[0])
        if len(set(resolved)) != len(resolved):
            raise ValueError('GPU name hints must resolve to distinct adapters')
        return resolved
    devices = match(spec.device_name_hints)
    if devices is not None:
        return devices, spec.gpu_layers
    if spec.fallback_device_name_hints:
        devices = match(spec.fallback_device_name_hints)
        if devices is not None:
            log.warning('%s using configured GPU fallback: %s, %s layers', spec.id, devices, spec.fallback_gpu_layers)
            return devices, spec.fallback_gpu_layers
    raise RuntimeError(f'Configured GPU for {spec.id} not found; adjust device_name_hints in models.yaml')


def model_command(spec, model_file=None, *, reserve_mb=1024, routing_path=None):
    prefix = executable_prefix()
    help_text = supported_options(prefix)
    def supports(flag):
        return re.search(r'(?<![\w-])'+re.escape(flag)+r'(?![\w-])', help_text) is not None
    endpoint = urlsplit(spec.endpoint)
    source = ['-hf', f'{spec.hf_repo}:{spec.quantization}']
    if model_file is not None:
        path = Path(model_file).resolve()
        if not path.is_file() or path.name != spec.model_file:
            raise ValueError(f'Local model must be an existing {spec.model_file} file')
        source = ['-m', str(path)]
    projector = getattr(spec, 'vision_projector', None)
    if projector:
        if not supports('--mmproj'):
            raise RuntimeError('This llama.cpp build cannot load the configured vision projector')
        from huggingface_hub import try_to_load_from_cache
        if model_file is None and spec.hf_repo:
            cached_model = try_to_load_from_cache(spec.hf_repo, spec.model_file)
            if isinstance(cached_model, str) and Path(cached_model).is_file():
                source = ['-m', str(Path(cached_model).resolve())]
        local = Path(model_file).resolve().parent / projector if model_file else None
        cached = try_to_load_from_cache(spec.hf_repo, projector) if spec.hf_repo else None
        projector_path = local if local is not None and local.is_file() else (
            Path(cached) if isinstance(cached, str) and Path(cached).is_file() else None)
        if projector_path is None:
            raise RuntimeError(f'Configured vision projector {projector} is missing from the local model cache')
        source += ['--mmproj', str(projector_path.resolve())]
        # Keep vision encoding on CPU so the resident LLM retains its GPU
        # headroom. No second language server or duplicate weights are needed.
        if supports('--no-mmproj-offload'):
            source += ['--no-mmproj-offload']
    devices, layers = resolve_devices(spec, prefix, reserve_mb=reserve_mb, routing_path=routing_path)
    flags = ['--alias', spec.api_model, '--host', '127.0.0.1', '--port', str(endpoint.port or 80),
             '-c', str((spec.context_length or 4096) * spec.parallel), '--parallel', str(spec.parallel),
             '-ngl', str(layers)]
    if not spec.jinja_enabled:
        flags += ['--no-jinja']
    if not layers:
        flags += ['--device', 'none']
        if supports('--no-op-offload'): flags += ['--no-op-offload']
    elif devices:
        flags += ['--device', ','.join(devices)]
        if spec.gpu_selection in {'most_vram', 'smallest_8gb'}:
            flags += ['--split-mode', 'none', '--main-gpu', '0']
            # New builds hide tensor placement at the default info level. Trace
            # exposes allocation/offload evidence; do not enable verbose/debug
            # or prompt logging.
            if supports('--log-verbosity'):
                flags += ['--log-verbosity', '4']
    if spec.split_mode: flags += ['--split-mode', spec.split_mode]
    if spec.tensor_split: flags += ['--tensor-split', ','.join(map(str, spec.tensor_split))]
    if supports('--cache-type-k') and supports('--cache-type-v') and supports('--flash-attn'):
        flags += ['--flash-attn', 'on', '-ctk', spec.kv_key_type, '-ctv', spec.kv_value_type]
    else:
        log.warning('%s: quantized KV/Flash Attention flags unavailable; using build defaults', spec.id)
    if supports('--reasoning') and not spec.thinking_enabled:
        flags += ['--reasoning', 'off']
    if supports('--load-mode'):
        flags += ['--load-mode', 'mmap' if spec.mmap else 'none']
    elif supports('--mmap') and spec.mmap:
        flags += ['--mmap']
    elif supports('--no-mmap') and not spec.mmap:
        flags += ['--no-mmap']
    # Builds with only --no-mmap already default to mmap. Never add --mlock.
    if spec.no_host:
        if not supports('--no-host'):
            raise RuntimeError('This llama.cpp build does not support the requested no_host experiment')
        flags += ['--no-host']
    return prefix + source + flags

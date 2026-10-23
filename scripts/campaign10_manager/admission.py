"""Fresh configured endpoint identity; historical campaign PIDs are immutable."""
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
import psutil
from hanni.config.loader import load_config
from scripts.campaign8_ui.streaming import resource_gate, _metadata, StreamingAdmissionError
ROOT = Path(__file__).resolve().parents[2]

def original_model_admission(expected_process=None):
    memory = psutil.virtual_memory()
    resource = {'available_ram_bytes': memory.available, 'used_percent': memory.percent}
    resource_gate(resource)
    spec = load_config(ROOT / 'config', data_dir=ROOT / 'data/campaign10-manager', env={}).models.supervisor
    if urlsplit(spec.endpoint) != urlsplit('http://127.0.0.1:8080/v1'):
        raise StreamingAdmissionError('The configured model must remain the fixed loopback endpoint.')
    listeners = [c for c in psutil.net_connections(kind='tcp') if c.status == psutil.CONN_LISTEN and c.laddr.port == 8080]
    if not listeners or any((c.laddr.ip not in {'127.0.0.1', '::1'} for c in listeners)):
        raise StreamingAdmissionError('No exclusively loopback configured model listener.')
    pids = {c.pid for c in listeners}
    if None in pids or len(pids) != 1:
        raise StreamingAdmissionError('The model listener has no unique process identity.')
    process = psutil.Process(next(iter(pids)))
    if not process.is_running() or process.name().casefold() != 'llama-server.exe':
        raise StreamingAdmissionError('The endpoint is not owned by a running llama-server.')
    health = _metadata('/health')
    props = _metadata('/props')
    slots = _metadata('/slots')
    loaded = props.get('model_path')
    if not isinstance(loaded, str) or Path(loaded).name != spec.model_file or (not Path(loaded).is_file()):
        raise StreamingAdmissionError('Actual loaded weights differ from the configured existing file.')
    command = process.cmdline()
    explicit = next((command[command.index(flag) + 1] for flag in ('-m', '--model') if flag in command and command.index(flag) + 1 < len(command)), None)
    if explicit is not None and Path(explicit).resolve() != Path(loaded).resolve():
        raise StreamingAdmissionError('Process model argument and actual loaded file disagree.')
    identity = {'pid': process.pid, 'create_time': process.create_time(), 'name': process.name(), 'model_path': loaded, 'endpoint': spec.endpoint, 'command_sha256': hashlib.sha256('\x00'.join(command).encode('utf8')).hexdigest(), 'identity_source': 'fresh_props_bound_to_unique_pid_owned_loopback_socket'}
    if expected_process is not None and identity != expected_process:
        raise StreamingAdmissionError('Model identity changed during the admitted session.')
    if health.get('status') != 'ok' or props.get('model_alias') != spec.api_model:
        raise StreamingAdmissionError('Model health or configured alias is not verified.')
    if not isinstance(slots, list) or not slots or any((not isinstance(slot, dict) or slot.get('is_processing') is not False for slot in slots)):
        raise StreamingAdmissionError('The original model endpoint does not have verified idle slots.')
    final_listeners = [c for c in psutil.net_connections(kind='tcp') if c.status == psutil.CONN_LISTEN and c.laddr.port == 8080]
    current = {c.pid for c in final_listeners}
    command_hash = hashlib.sha256('\x00'.join(process.cmdline()).encode('utf8')).hexdigest()
    if current != {process.pid} or any((c.laddr.ip not in {'127.0.0.1', '::1'} for c in final_listeners)) or process.create_time() != identity['create_time'] or (command_hash != identity['command_sha256']):
        raise StreamingAdmissionError('Endpoint identity changed while reading model metadata.')
    return {'resource': resource, 'process': identity, 'health': health, 'props': {'model_path': loaded, 'model_alias': props.get('model_alias'), 'total_slots': props.get('total_slots'), 'modalities': props.get('modalities')}, 'slots': [{'id': slot.get('id'), 'is_processing': slot.get('is_processing')} for slot in slots]}

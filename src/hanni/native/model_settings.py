"""Model selection shared by the dashboard and its owning launcher.

Only nonsecret settings cross the on-disk mailbox. The launcher owns model
processes and is the only process allowed to replace them.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
import uuid

from .provider import NativeClient, normalize_endpoint

MIN_CONTEXT = 65536
MAX_CONTEXT = 262144
LOCAL_MODELS = (
    ('MiniCPM 2B', 'MiniCPM5-2B-Q4_K_M.gguf'),
    ('K2 3.7B', 'K2-Horizon-4B-Q4_K_M.gguf'),
    ('K2 7B', 'K2-Horizon-7B-Q4_K_M.gguf'),
    ('Qwen 3.5 4B', 'Qwen3.5-4B-Q4_K_M.gguf'),
    ('Qwen 3.5 9B', 'Qwen3.5-9B-Q4_K_M.gguf'),
)


def context_size(value):
    if type(value) is not int or not MIN_CONTEXT <= value <= MAX_CONTEXT or value % 1024:
        raise ValueError('Choose a context from 64K to 256K in steps of 1024 tokens.')
    return value


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def credential_vault():
    if os.name == 'nt':
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()
    import keyring
    vault = keyring.get_keyring()
    if type(vault).__module__ not in {'keyring.backends.macOS', 'keyring.backends.SecretService'}:
        raise RuntimeError('Secure credential storage is unavailable. Use HANNI_MODEL_API_KEY instead.')
    return vault


def stored_api_key(reference):
    try:
        value = credential_vault().get_password('HANNI.Models.v1', reference)
    except Exception:
        raise RuntimeError('The saved model API key is unavailable. Enter it again in Models.') from None
    if not value:
        raise RuntimeError('The saved model API key is missing. Enter it again in Models.')
    from hanni.logs.redaction import register_secret
    register_secret('model-api', value)
    return value


def model_config(selection):
    return {'id': 'stick-brain', 'api_model': selection.get('api_model') or 'stick-brain',
            'endpoint': selection['endpoint'], 'context_length': selection['context'],
            'source': selection['source'], 'api_key_ref': selection.get('api_key_ref'),
            'model_file': selection.get('local_model') or selection.get('api_model')}


class ModelSettings:
    def __init__(self, root=None, models_dir=None):
        self.root = Path(root) if root else None
        self.models_dir = Path(models_dir) if models_dir else None
        self.lock = threading.RLock()

    @classmethod
    def from_env(cls):
        return cls(os.environ.get('HANNI_MODEL_STATE'), os.environ.get('HANNI_MODELS_DIR'))

    def active(self):
        return read_json(self.root / 'model-selection.json') if self.root else None

    def profiles(self):
        saved = read_json(self.root / 'model-profiles.json', []) if self.root else []
        active = self.active()
        if active and active not in saved:
            saved.append(active)
        return saved

    def remember_profile(self, selection):
        if not self.root:
            return
        identity = lambda value: (value.get('source'), value.get('endpoint'), value.get('local_model') or value.get('api_model'))
        profiles = [p for p in self.profiles() if identity(p) != identity(selection)]
        atomic_json(self.root / 'model-profiles.json', (profiles + [selection])[-50:])

    def change(self):
        return read_json(self.root / 'model-change.json') if self.root else None

    def pending(self):
        return (self.change() or {}).get('status') in {'pending', 'applying'}

    def mark(self, request, status, detail):
        atomic_json(self.root / 'model-change.json', {**request, 'status': status, 'detail': detail})

    def inventory(self):
        from .gguf_context import context_limit
        known = dict((file, name) for name, file in LOCAL_MODELS)
        if self.models_dir and self.models_dir.is_dir():
            for file in sorted(self.models_dir.glob('*.gguf')):
                if file.name.lower().startswith('mmproj'):
                    continue  # Vision projectors accompany models; they are not language models.
                known.setdefault(file.name, file.stem)
        return [{'id': file, 'name': name, 'installed': bool(self.models_dir and (self.models_dir / file).is_file()),
                 'max_context': min(MAX_CONTEXT, context_limit(self.models_dir / file) or MAX_CONTEXT) if self.models_dir else MAX_CONTEXT}
                for file, name in known.items()]

    @staticmethod
    def public(selection):
        if not selection:
            return None
        return {**{key: value for key, value in selection.items() if key != 'api_key_ref'},
                'has_api_key': bool(selection.get('api_key_ref'))}

    def snapshot(self):
        change = self.change()
        return {'available': bool(self.root and os.environ.get('HANNI_MODEL_CONTROL') == '1'),
                'active': self.public(self.active()), 'local_models': self.inventory(),
                'min_context': MIN_CONTEXT, 'max_context': MAX_CONTEXT,
                'change': None if not change else {key: change.get(key) for key in ('id', 'status', 'detail')},
                'environment_key': bool(os.environ.get('HANNI_MODEL_API_KEY'))}

    def output_model(self):
        from .provider import load_model
        if not self.root or not (self.root / 'models.native.yaml').is_file():
            raise RuntimeError('Output settings require the native model session. Start Hanni with START_HANNI or START_BRAIN.')
        return load_model(self.root / 'models.native.yaml', output_settings=False)

    def output_snapshot(self):
        from .output_settings import OutputSettings
        try:
            model = self.output_model()
        except RuntimeError as exc:
            return {'available': False, 'reason': str(exc)}
        return OutputSettings(self.root).snapshot(model)

    def save_output(self, body):
        from .output_settings import OutputSettings
        with self.lock:
            if self.pending():
                raise RuntimeError('Wait for the current model change to finish.')
            return OutputSettings(self.root).save(self.output_model(), body)

    def reasoning_model(self):
        from .output_settings import OutputSettings
        return OutputSettings(self.root).apply(self.output_model())

    def reasoning_snapshot(self):
        from .reasoning_settings import ReasoningSettings
        try:
            model = self.reasoning_model()
        except RuntimeError as exc:
            return {'available': False, 'reason': str(exc)}
        return ReasoningSettings(self.root).snapshot(model, NativeClient(model).status())

    def save_reasoning(self, body):
        from .reasoning_settings import ReasoningSettings
        with self.lock:
            if self.pending():
                raise RuntimeError('Wait for the current model change to finish.')
            model = self.reasoning_model()
            return ReasoningSettings(self.root).save(model, body, NativeClient(model).status())

    def validate(self, body):
        if not isinstance(body, dict) or set(body) - {'operation', 'id', 'source', 'local_model', 'endpoint', 'api_model', 'api_key', 'context'}:
            raise ValueError('Invalid model settings.')
        selection = {'source': body.get('source'), 'context': context_size(body.get('context'))}
        if selection['source'] == 'local':
            file = body.get('local_model')
            if not isinstance(file, str) or file not in {model['id'] for model in self.inventory() if model['installed']}:
                raise ValueError('Select an installed local model.')
            path = (self.models_dir / file).resolve()
            if not path.is_relative_to(self.models_dir.resolve()):
                raise ValueError('Model must be inside the local models directory.')
            from .gguf_context import context_limit
            maximum = context_limit(path)
            if maximum and selection['context'] > maximum:
                raise ValueError(f'This model supports up to {maximum // 1024}K context. Choose K2 for a 256K window.')
            selection['local_model'] = file
            return selection
        if selection['source'] != 'api':
            raise ValueError('Choose a local model or an API connection.')
        endpoint, api_model = body.get('endpoint'), body.get('api_model')
        if not isinstance(endpoint, str) or len(endpoint) > 2048:
            raise ValueError('Enter the API base URL.')
        selection['endpoint'] = normalize_endpoint(endpoint)
        from urllib.parse import urlsplit
        parts = urlsplit(selection['endpoint'])
        if parts.scheme != 'https' and parts.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Use HTTPS for a remote model API.')
        if not isinstance(api_model, str) or not 1 <= len(api_model.strip()) <= 256 or any(ord(c) < 32 for c in api_model):
            raise ValueError('Enter the exact API model ID.')
        selection['api_model'] = api_model.strip()
        key = body.get('api_key', '')
        if not isinstance(key, str) or len(key) > 8192 or any(ord(c) < 32 for c in key):
            raise ValueError('Enter a valid API key.')
        active = self.active() or {}
        if not key and active.get('source') == 'api' and active.get('endpoint') == selection['endpoint']:
            selection['api_key_ref'] = active.get('api_key_ref')
        return selection

    def execute(self, body):
        with self.lock:
            if not self.root or os.environ.get('HANNI_MODEL_CONTROL') != '1':
                raise RuntimeError('Model switching requires START_HANNI with the supervised launcher.')
            if body.get('operation') not in {'test', 'apply'}:
                raise ValueError('Choose Test connection or Apply model.')
            request_id = body.get('id')
            try:
                request_id = str(uuid.UUID(request_id))
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Invalid model request ID.') from None
            prior = self.change()
            selection = self.validate(body)
            if prior and prior.get('id') == request_id and body['operation'] == 'apply':
                # An uncertain retry cannot become a second model restart.
                comparable = {k: v for k, v in selection.items() if k != 'api_key_ref'}
                previous = {k: v for k, v in prior['selection'].items() if k != 'api_key_ref'}
                if comparable != previous:
                    raise ValueError('Request ID was already used with different model settings.')
                return self.snapshot()
            if self.pending():
                raise RuntimeError('A model change is already in progress.')
            key = body.get('api_key') or None
            if selection['source'] == 'api':
                client = NativeClient(model_config(selection), api_key=key)
                status = client.status()
                if not status['ready']:
                    raise ValueError(status.get('detail') or 'Could not connect to the requested API model.')
                if status.get('context_verified') and status['context'] < selection['context']:
                    raise ValueError(f"This server reports a {status['context']:,}-token context, below the requested size.")
            if body['operation'] == 'test':
                return {'connected': True, 'detail': 'The API advertises this model. Actual context and tool support depend on the provider.'}
            if key and selection['source'] == 'api':
                reference = uuid.uuid4().hex
                try:
                    credential_vault().set_password('HANNI.Models.v1', reference, key)
                except Exception:
                    raise RuntimeError('Could not save the API key securely. Set HANNI_MODEL_API_KEY or retry credential storage.') from None
                selection['api_key_ref'] = reference
            request = {'id': request_id, 'selection': selection, 'created': time.time()}
            active = self.active()
            if active:
                self.remember_profile(active)
            self.remember_profile(selection)
            self.mark(request, 'pending', 'Waiting for the launcher to switch models…')
            return self.snapshot()

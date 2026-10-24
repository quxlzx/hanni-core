"""Per-model generation limits, applied when a new native task loads its model."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MAX_OUTPUT_TOKENS = 65536


def model_identity(model):
    from .provider import normalize_endpoint
    identity = [normalize_endpoint(model['endpoint']), model.get('api_model') or model['id'],
                str(model.get('model_file', ''))]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def output_ceiling(model):
    # Reserve input room even when the requested output approaches the context.
    return max(1, min(MAX_OUTPUT_TOKENS, int(model.get('context_length', 16384)) - 2048))


class OutputSettings:
    def __init__(self, root=None):
        self.root = Path(root) if root else None

    def preferences(self):
        from .model_settings import read_json
        return read_json(self.root / 'output-settings.json', {}) if self.root else {}

    def snapshot(self, model):
        maximum = output_ceiling(model)
        default = min(maximum, max(1, int(model.get('native_max_tokens', 1500))))
        saved = self.preferences().get(model_identity(model), {}).get('max_tokens')
        customized = type(saved) is int and saved > 0
        return {'available': bool(self.root), 'model_id': model_identity(model),
                'model': model.get('model_file') or model.get('api_model') or model['id'],
                'max_tokens': min(saved, maximum) if customized else default,
                'default_max_tokens': default, 'minimum': 1, 'maximum': maximum,
                'customized': customized}

    def apply(self, model):
        if not self.root:
            return model
        settings = self.snapshot(model)
        return {**model, 'native_max_tokens': settings['max_tokens']}

    def save(self, model, body):
        from .model_settings import atomic_json
        if not self.root:
            raise RuntimeError('Persistent output settings are unavailable in this launcher.')
        if not isinstance(body, dict) or set(body) != {'id', 'model_id', 'max_tokens'}:
            raise ValueError('Choose an output-token limit for the current model.')
        identity = model_identity(model)
        if body['model_id'] != identity:
            raise ValueError('The active model changed. Refresh output settings before saving.')
        value = body['max_tokens']
        maximum = output_ceiling(model)
        if value is not None and (type(value) is not int or not 1 <= value <= maximum):
            raise ValueError(f'Choose a whole number from 1 to {maximum:,} output tokens.')
        preferences = self.preferences()
        if value is None:
            preferences.pop(identity, None)
        else:
            preferences[identity] = {'max_tokens': value}
        atomic_json(self.root / 'output-settings.json', preferences)
        return self.snapshot(model)

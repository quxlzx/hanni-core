"""Durable per-model reasoning controls shared with the /reasoning command."""
from pathlib import Path

from .output_settings import model_identity


def reasoning_identity(model):
    from .provider import normalize_endpoint
    return (normalize_endpoint(model['endpoint']) + '|' + str(model.get('api_model') or model['id']).strip()
            + '|' + str(model.get('model_file', '')))


def budget_ceiling(model):
    return max(0, int(model.get('native_max_tokens', 1500)) - 1)


class ReasoningSettings:
    def __init__(self, root=None):
        self.root = Path(root) if root else None

    def preferences(self):
        from .model_settings import read_json
        return read_json(self.root / 'reasoning-settings.json', {}) if self.root else {}

    def values(self, model):
        saved = self.preferences().get(reasoning_identity(model), {})
        effort = saved.get('effort', model.get('native_reasoning_effort'))
        budget = saved.get('budget', model.get('native_reasoning_budget'))
        if effort == 'none' and model.get('source') == 'local':
            budget = 0
        if type(budget) is int and budget >= 0:
            budget = min(budget, budget_ceiling(model))
        return {'effort': effort, 'budget': budget}

    def snapshot(self, model, status):
        saved = self.preferences().get(reasoning_identity(model), {})
        budget = saved.get('budget')
        if type(budget) is int and budget >= 0:
            budget = min(budget, budget_ceiling(model))
        values = self.values(model)
        return {'available': bool(self.root), 'model_id': model_identity(model),
                'ready': bool(status.get('ready')), 'reason': status.get('detail'),
                'effort_levels': status.get('reasoning_levels', []),
                'can_disable': bool(status.get('reasoning_disable_supported')),
                'budget_supported': bool(status.get('reasoning_budget_supported')),
                'effort': saved.get('effort'), 'budget': budget,
                'effective_effort': values['effort'], 'effective_budget': values['budget'],
                'max_budget': budget_ceiling(model), 'output_limit': int(model.get('native_max_tokens', 1500)),
                'customized': bool(saved)}

    def save(self, model, body, status):
        from .model_settings import atomic_json
        if not self.root:
            raise RuntimeError('Persistent reasoning settings are unavailable in this launcher.')
        if not isinstance(body, dict) or set(body) != {'id', 'model_id', 'effort', 'budget'}:
            raise ValueError('Choose reasoning effort and a reasoning-token budget.')
        if body['model_id'] != model_identity(model):
            raise ValueError('The active model changed. Refresh reasoning settings before saving.')
        effort, budget = body['effort'], body['budget']
        reset = effort is None and budget is None
        if not reset and not status.get('ready'):
            raise RuntimeError('Connect the active model before changing reasoning settings.')
        allowed = set(status.get('reasoning_levels', []))
        if status.get('reasoning_disable_supported'):
            allowed.add('none')
        if effort is not None and (not isinstance(effort, str) or effort not in allowed):
            raise ValueError('This model does not advertise that reasoning-effort setting.')
        if budget is not None:
            if not status.get('reasoning_budget_supported'):
                raise ValueError('This connection does not expose a supported reasoning-token budget.')
            if type(budget) is not int or not -1 <= budget <= budget_ceiling(model):
                raise ValueError(f'Use -1 for no separate cap, or 0–{budget_ceiling(model):,} reasoning tokens.')
            if effort == 'none':
                raise ValueError('Choose reasoning Off or a token budget, rather than both.')
        preferences = self.preferences()
        identity = reasoning_identity(model)
        setting = {key: value for key, value in {'effort': effort, 'budget': budget}.items() if value is not None}
        if setting:
            preferences[identity] = setting
        else:
            preferences.pop(identity, None)
        atomic_json(self.root / 'reasoning-settings.json', preferences)
        return self.snapshot(model, status)

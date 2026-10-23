"""Model-facing shadow evaluator: no memory mutations or external tool calls."""
import math
import time
import threading
from .questions import CAPTURE, IMPORTANCE, SENSITIVE, RELATION, RELEVANCE

ALLOWED_KEYS = frozenset({'utterance', 'existing_memory', 'request', 'candidate_memory'})
MAX_FIELD_LEN = 4096

class InputError(ValueError):
    pass


def validate(payload):
    if not isinstance(payload, dict):
        raise InputError('Expected a JSON object')
    if set(payload) - ALLOWED_KEYS:
        raise InputError('Unknown or unauthorized fields')
    if not payload:
        raise InputError('Missing input')
    for k, v in payload.items():
        if not isinstance(v, str) or not v.strip() or len(v) > MAX_FIELD_LEN:
            raise InputError(f'Invalid or oversized field: {k}')
    if 'existing_memory' in payload and 'utterance' not in payload:
        raise InputError('existing_memory requires utterance')
    if ('request' in payload) != ('candidate_memory' in payload):
        raise InputError('request and candidate_memory must be supplied together')
    if 'utterance' not in payload and 'request' not in payload:
        raise InputError('At least utterance or request required')
    return payload


def _num(v, key):
    n = float(v)
    if not math.isfinite(n):
        raise ValueError(f'Non-finite {key}')
    return n


class ShadowEngine:
    """A single loaded model, serialized predictions, typed sanitized output."""
    def __init__(self, predictor):
        self.predictor = predictor
        self.lock = threading.Lock()

    def evaluate(self, payload):
        p = validate(payload)
        started = time.perf_counter()
        out = {}
        # Keep checkpoint's exact training-time question wording.
        with self.lock:
            if 'utterance' in p:
                a = self.predictor.predict(p['utterance'], {
                    'capture': CAPTURE, 'importance': IMPORTANCE, 'sensitive': SENSITIVE
                })['answers']
                out['capture'] = _num(a['capture']['noul'], 'capture') >= .5
                out['importance'] = _num(a['importance']['score'], 'importance')
                out['sensitive'] = _num(a['sensitive']['noul'], 'sensitive') >= .5
            if 'existing_memory' in p:
                state = f"EXISTING MEMORY: {p['existing_memory']}\nNEW UTTERANCE: {p['utterance']}"
                a = self.predictor.predict(state, {'relation': RELATION})['answers']
                relation = a['relation']['choice']
                if relation not in {'add', 'supersede', 'ignore', 'verify'}:
                    raise ValueError('Unknown relation label')
                out['relation'] = relation
            if 'request' in p:
                state = f"CURRENT REQUEST: {p['request']}\nCANDIDATE MEMORY: {p['candidate_memory']}"
                a = self.predictor.predict(state, {'relevance': RELEVANCE})['answers']
                out['relevance'] = _num(a['relevance']['noul'], 'relevance') >= .5
        return out, round((time.perf_counter() - started) * 1000, 2)

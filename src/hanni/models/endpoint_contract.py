"""Shared endpoint evidence v1. Identical module ships with Control Center.

Evidence is advisory: this contract neither supplies credentials nor authorizes
tasks, service lifecycle, remote context, or unmeasured capability claims.
"""
import hashlib
import ipaddress
import json
import math
import re
import time
from urllib.parse import urlsplit

FEATURES = ('chat', 'tool_calling', 'structured_output', 'streaming', 'reasoning')


class ContractError(ValueError):
    pass


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError('Invalid bounded endpoint capacity.')


def _stamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ContractError('Invalid endpoint evidence timestamp.')


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ContractError('Endpoint proof requires an exact evidence digest.')


def _validate(frame, *, now=None):
    if not isinstance(frame, dict) or set(frame) != {'version', 'endpoint_id', 'model_id',
            'loaded_model_id', 'binding', 'auth_reference', 'features', 'context',
            'health', 'resources', 'concurrency', 'cancellation', 'performance'}:
        raise ContractError('Invalid endpoint evidence fields.')
    if type(frame['version']) is not int or frame['version'] != 1:
        raise ContractError('Unsupported endpoint evidence version.')
    for field in ('endpoint_id', 'model_id'):
        if not isinstance(frame[field], str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', frame[field]):
            raise ContractError('Invalid stable endpoint/model identity.')
    _digest(frame['binding'])
    if frame['loaded_model_id'] is not None and not isinstance(frame['loaded_model_id'],str):
        raise ContractError('Invalid loaded-model identity.')
    auth = frame['auth_reference']
    if (not isinstance(auth, dict) or set(auth) != {'kind', 'name'}
            or auth['kind'] not in {'none', 'environment', 'protected_file', 'ssh'}
            or not isinstance(auth['name'], str) or not re.fullmatch('[A-Za-z0-9_.-]{0,128}', auth['name'])):
        raise ContractError('Authentication must be a symbolic reference, never a secret.')
    if set(frame['features']) != set(FEATURES):
        raise ContractError('Every endpoint feature must have an explicit evidence state.')
    for feature in frame['features'].values():
        if not isinstance(feature, dict) or set(feature) != {'advertised', 'verified', 'evidence_sha256'}:
            raise ContractError('Invalid feature evidence.')
        if (feature['advertised'] is not None and type(feature['advertised']) is not bool) or type(feature['verified']) is not bool:
            raise ContractError('Invalid feature state.')
        if feature['evidence_sha256'] is not None: _digest(feature['evidence_sha256'])
        if feature['verified'] and (feature['advertised'] is False or not feature['evidence_sha256']):
            raise ContractError('An advertised feature is not a verified capability.')
    context = frame['context']
    if set(context) != {'configured', 'reported', 'measured_usable', 'evidence_sha256'}:
        raise ContractError('Invalid context evidence.')
    for field in ('configured', 'reported', 'measured_usable'):
        if context[field] is not None: _integer(context[field], 1, 1048576)
    if context['evidence_sha256'] is not None: _digest(context['evidence_sha256'])
    if context['measured_usable'] is not None:
        if not context['evidence_sha256']: raise ContractError('Allocated context is not measured usable context.')
        if any(context['measured_usable'] > context[k] for k in ('configured', 'reported') if context[k] is not None):
            raise ContractError('Measured context exceeds configured/reported capacity.')
    health = frame['health']
    if set(health) != {'status', 'sampled_at', 'freshness_seconds'} or health['status'] not in {'healthy', 'busy', 'unavailable', 'unknown'}:
        raise ContractError('Invalid health evidence.')
    _stamp(health['sampled_at']); _integer(health['freshness_seconds'], 1, 60)
    if health['status'] in {'healthy', 'busy'} and frame['loaded_model_id'] != frame['model_id']:
        raise ContractError('Healthy endpoint has a mismatched loaded model.')
    resources = frame['resources']
    if set(resources) != {'sampled_at', 'ram_available_bytes', 'vram_free_bytes', 'available'}:
        raise ContractError('Invalid resource evidence.')
    if resources['sampled_at'] is not None: _stamp(resources['sampled_at'])
    for field in ('ram_available_bytes', 'vram_free_bytes'):
        if resources[field] is not None: _integer(resources[field], 0, 2**60)
    if resources['available'] is not None and type(resources['available']) is not bool: raise ContractError('Invalid availability state.')
    if resources['available'] is True and any(resources[k] is None for k in ('sampled_at','ram_available_bytes','vram_free_bytes')):
        raise ContractError('Unknown resources cannot claim availability.')
    slots = frame['concurrency']
    if set(slots) != {'configured', 'active', 'queue_depth'}: raise ContractError('Invalid concurrency evidence.')
    _integer(slots['configured'], 1, 16)
    for field in ('active','queue_depth'):
        if slots[field] is not None: _integer(slots[field], 0, 1024)
    if frame['cancellation'] not in {'connection_close_best_effort', 'request_scoped', 'unverified'}:
        raise ContractError('Invalid cancellation guarantee.')
    if set(frame['performance']) != {'sample_count','ttft_p50_ms','ttft_p95_ms','total_p50_ms','total_p95_ms'}:
        raise ContractError('Invalid performance receipts.')
    _integer(frame['performance']['sample_count'], 0, 10000000)
    for key,value in frame['performance'].items():
        if key != 'sample_count' and value is not None: _stamp(value)
    now = time.time() if now is None else now
    fresh = 0 <= now-health['sampled_at'] <= health['freshness_seconds']
    return {'valid':True, 'health_fresh':fresh,
            'identity_matches': frame['loaded_model_id']==frame['model_id']}


def validate(frame, *, now=None):
    try:
        return _validate(frame,now=now)
    except (TypeError,KeyError,OverflowError) as exc:
        raise ContractError('Malformed endpoint evidence was rejected.') from exc


def build(*, endpoint_id, model_id, loaded_model_id, binding, configured_context,
          reported_context=None, status='unknown', sampled_at=None, concurrency=1,
          active=None, auth_kind='none', auth_name='', advertised=(), reasoning=None):
    frame = {'version':1,'endpoint_id':endpoint_id,'model_id':model_id,'loaded_model_id':loaded_model_id,
        'binding':hashlib.sha256(json.dumps(binding,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        'auth_reference':{'kind':auth_kind,'name':auth_name},
        'features':{k:{'advertised':(reasoning if k=='reasoning' else k in advertised),
                       'verified':False,'evidence_sha256':None} for k in FEATURES},
        'context':{'configured':configured_context,'reported':reported_context,
                   'measured_usable':None,'evidence_sha256':None},
        'health':{'status':status,'sampled_at':time.time() if sampled_at is None else sampled_at,'freshness_seconds':10},
        'resources':{'sampled_at':None,'ram_available_bytes':None,'vram_free_bytes':None,'available':None},
        'concurrency':{'configured':concurrency,'active':active,'queue_depth':None},
        'cancellation':'connection_close_best_effort',
        'performance':{'sample_count':0,'ttft_p50_ms':None,'ttft_p95_ms':None,'total_p50_ms':None,'total_p95_ms':None}}
    validate(frame)
    return frame

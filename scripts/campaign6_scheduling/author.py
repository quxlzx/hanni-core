"""Prospective scheduling controls; references never enter the executor."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
CATEGORIES = ('correct_worker_selection', 'worker_unavailable', 'worker_busy', 'context_too_large', 'insufficient_vram', 'multiple_eligible_workers', 'parallel_tasks', 'queue_saturation', 'safe_reassignment', 'network_interruption', 'result_verification')

def worker(identifier='w0', **values):
    return dict(id=identifier, enabled=True, concurrency=1, interactive_reserve=0, categories=['synthetic', 'project', 'conversation'], capabilities=['analysis', 'structured_json'], context_configured=32768, context_reported=32768, verified_context=32768, resources={'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': None}, response_behavior='complete', **values)

def changed(identifier='w0', **values):
    result = worker(identifier)
    result.update(values)
    return result

def request(**values):
    result = dict(messages=[{'role': 'user', 'content': 'Synthetic delivery request.'}], categories=['synthetic'], max_tokens=16, queue_seconds=0.15)
    result.update(values)
    return result

def build():
    cases = []
    oracles = []
    counts = {}

    def emit(category, label, workers, expected, operation='selection', req=None, **values):
        counts[category] = counts.get(category, 0) + 1
        identifier = f'C6DEV-{category}-{counts[category]:02d}'
        cases.append(dict(id=identifier, category=category, description=label, scenario=operation, workers=workers, request=request(**req or {}), scope='original_guarded_controlled_provider', **values))
        oracles.append(dict(id=identifier, expected=dict(all_released=True, **expected)))
    w0 = worker()
    w1 = worker('w1')
    emit(CATEGORIES[0], 'Pinned placement overrides faster eligible neighbor.', [changed(latency_ms=1), changed('w1', latency_ms=100)], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}}, req={'allowed_worker_ids': ['w1']})
    emit(CATEGORIES[0], 'Trusted synthetic category filters conversation-only node.', [changed(categories=['conversation']), w1], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}})
    emit(CATEGORIES[0], 'Structured schema requires original structured capability.', [changed(capabilities=['analysis']), w1], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}}, req={'response_format': {'type': 'json_object'}})
    emit(CATEGORIES[0], 'Verified allocation filters otherwise fast node.', [changed(verified_context=64, latency_ms=1), changed('w1', latency_ms=100)], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}})
    emit(CATEGORIES[0], 'Reserved interactive-only node excludes background work.', [changed(interactive_reserve=1), w1], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}})
    emit(CATEGORIES[0], 'Strata-compatible protocol remains original bounded HTTP.', [changed(protocol='strata_openai')], {'worker_id': 'w0', 'dispatches': {'w0': 1}})
    for label, changes in [('Disabled worker', {'enabled': False}), ('Unhealthy observation', {'health': 'unhealthy'}), ('Stale heartbeat', {'heartbeat_age_seconds': 31}), ('Future heartbeat', {'heartbeat_age_seconds': -5}), ('Different loaded model', {'health_model': 'unregistered'}), ('Absent context proof', {'verified_context': None})]:
        emit(CATEGORIES[1], label, [changed(**changes)], {'error': True, 'dispatches': {'w0': 0}})
    emit(CATEGORIES[2], 'Single occupied slot queues second request.', [w0], {'dispatches': {'w0': 2}, 'queue_seen': True, 'maximum_overlap': 1}, 'background_queue', background=[{'worker_id': 'w0', 'label': 'background'}])
    emit(CATEGORIES[2], 'Reserve keeps second background request queued.', [changed(concurrency=2, interactive_reserve=1)], {'dispatches': {'w0': 2}, 'queue_seen': True, 'maximum_overlap': 1}, 'background_queue', background=[{'worker_id': 'w0', 'label': 'background'}])
    emit(CATEGORIES[2], 'Interactive request uses reserve during background work.', [changed(concurrency=2, interactive_reserve=1)], {'dispatches': {'w0': 2}, 'maximum_overlap': 2, 'main_before_release': True}, 'background_queue', req={'interactive': True}, background=[{'worker_id': 'w0', 'label': 'background'}], release='after_main_entered')
    emit(CATEGORIES[2], 'Pinned busy neighbor does not block unrelated idle worker.', [w0, w1], {'worker_id': 'w1', 'dispatches': {'w0': 1, 'w1': 1}, 'main_before_release': True}, 'background_queue', req={'allowed_worker_ids': ['w1']}, background=[{'worker_id': 'w0', 'label': 'background'}], release='after_main_entered')
    emit(CATEGORIES[2], 'Queue deadline refuses occupied worker without dispatch.', [w0], {'error': True, 'dispatches': {'w0': 1}, 'queue_seen': True}, 'background_queue', req={'queue_seconds': 0.05}, background=[{'worker_id': 'w0', 'label': 'background'}], release='after_main_finished')
    emit(CATEGORIES[2], 'Queued cancellation leaves occupying job intact.', [w0], {'error': True, 'dispatches': {'w0': 1}, 'queue_seen': True, 'main_state': 'CANCELLED'}, 'background_queue', background=[{'worker_id': 'w0', 'label': 'background'}], control='cancel_queued')
    emit(CATEGORIES[3], 'Prompt plus output exceed verified capacity.', [changed(verified_context=512)], {'error': True, 'dispatches': {'w0': 0}}, req={'messages': [{'role': 'user', 'content': 'x' * 700}]})
    emit(CATEGORIES[3], 'Configured allocation cannot be overridden by imported proof.', [changed(context_configured=64)], {'error': True, 'dispatches': {'w0': 0}})
    emit(CATEGORIES[3], 'Reported current allocation constrains prior proof.', [changed(context_reported=64)], {'error': True, 'dispatches': {'w0': 0}})
    emit(CATEGORIES[3], 'Invalid output budget is rejected before queue.', [w0], {'error': True, 'dispatches': {'w0': 0}, 'job_count': 0}, req={'max_tokens': 8193})
    emit(CATEGORIES[3], 'Schema bytes participate in original context accounting.', [changed(verified_context=256)], {'error': True, 'dispatches': {'w0': 0}}, req={'response_format': {'type': 'json_schema', 'json_schema': {'name': 'fixture', 'schema': {'type': 'object', 'description': 'z' * 350}}}})
    emit(CATEGORIES[3], 'Small request fits genuine controlled current bounds.', [changed(context_configured=512, context_reported=512, verified_context=512)], {'dispatches': {'w0': 1}, 'main_state': 'COMPLETED'})
    remote = dict(node_id='fixture_remote', gpu='fixture_gpu')
    for label, vram in [('Zero GPU reserve', 0), ('Just below reserve', 256 * 1024 ** 2 - 1), ('Exact GPU reserve', 256 * 1024 ** 2), ('Unknown GPU reserve', None), ('Malformed GPU reserve', 'unknown')]:
        emit(CATEGORIES[4], label, [changed(**remote, resources={'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': vram})], {'error': vram != 256 * 1024 ** 2, 'dispatches': {'w0': int(vram == 256 * 1024 ** 2)}})
    emit(CATEGORIES[4], 'Old resource reading cannot certify current capacity.', [changed(**remote, resource_sample_age_seconds=60, resources={'ram_available_bytes': 8 * 1024 ** 3, 'vram_free_bytes': 2 * 1024 ** 3})], {'error': True, 'dispatches': {'w0': 0}})
    emit(CATEGORIES[5], 'Measured latency ranks eligible neighbors.', [changed(latency_ms=100), changed('w1', latency_ms=1)], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}})
    emit(CATEGORIES[5], 'Equal measurements use deterministic registered ID.', [changed(latency_ms=1), changed('w1', latency_ms=1)], {'worker_id': 'w0', 'dispatches': {'w0': 1, 'w1': 0}})
    emit(CATEGORIES[5], 'Current load selects unoccupied worker.', [changed(concurrency=2), w1], {'worker_id': 'w1', 'dispatches': {'w0': 1, 'w1': 1}, 'main_before_release': True}, 'background_queue', background=[{'worker_id': 'w0', 'label': 'background'}], release='after_main_entered')
    emit(CATEGORIES[5], 'Context constraint beats measured latency.', [changed(verified_context=64, latency_ms=1), changed('w1', latency_ms=100)], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}})
    emit(CATEGORIES[5], 'Privacy membership beats measured latency.', [changed(categories=['synthetic'], latency_ms=1), changed('w1', categories=['synthetic', 'memory'], latency_ms=100)], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}}, req={'categories': ['memory']})
    emit(CATEGORIES[5], 'Structured capability beats measured latency.', [changed(capabilities=['analysis'], latency_ms=1), changed('w1', latency_ms=100)], {'worker_id': 'w1', 'dispatches': {'w0': 0, 'w1': 1}}, req={'response_format': {'type': 'json_object'}})
    parallel = [([changed(concurrency=2)], 2, 2), ([w0, w1], 2, 2), ([w0], 3, 1), ([changed(concurrency=2)], 3, 2), ([changed(concurrency=2, interactive_reserve=1), changed('w1', concurrency=2, interactive_reserve=1)], 2, 2), ([changed(concurrency=2, interactive_reserve=1)], 2, 2)]
    for index, (workers, n, overlap) in enumerate(parallel):
        emit(CATEGORIES[6], ['Two slots on one worker', 'Independent nodes overlap', 'Single slot serializes three jobs', 'Two slots queue third job', 'Background jobs preserve per-node reserve', 'Interactive job shares reserved second slot'][index], workers, {'completed_results': n, 'maximum_overlap': overlap}, 'parallel', batch=n, release_after_entries=overlap, interactive_index=1 if index == 5 else None)
    emit(CATEGORIES[7], 'One waiting ticket exhausts configured queue.', [w0], {'queue_rejected': True, 'dispatches': {'w0': 2}}, 'queue_saturation', queue_limit=1, queued_count=1)
    emit(CATEGORIES[7], 'Two waiting tickets exhaust larger queue.', [w0], {'queue_rejected': True, 'dispatches': {'w0': 3}}, 'queue_saturation', queue_limit=2, queued_count=2)
    emit(CATEGORIES[7], 'Queue timeout never dispatches blocked request.', [w0], {'error': True, 'dispatches': {'w0': 1}, 'queue_seen': True}, 'background_queue', background=[{'worker_id': 'w0', 'label': 'background'}], release='after_main_finished', req={'queue_seconds': 0.05})
    emit(CATEGORIES[7], 'Within-class queue preserves admission order.', [w0], {'dispatches': {'w0': 4}, 'request_order': ['background', 'queued0', 'queued1', 'main']}, 'ordered_queue', queued_count=2)
    emit(CATEGORIES[7], 'Interactive tickets precede waiting background class.', [w0], {'dispatches': {'w0': 3}, 'request_order': ['background', 'main', 'queued0']}, 'ordered_queue', queued_count=1, req={'interactive': True})
    emit(CATEGORIES[7], 'Cancelled waiting ticket does not consume future slot.', [w0], {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'CANCELLED', 'queue_seen': True}, 'background_queue', background=[{'worker_id': 'w0', 'label': 'background'}], control='cancel_queued')
    for behavior, label in [('disconnect', 'Socket loss'), ('http500', 'HTTP failure'), ('truncated', 'Incomplete response'), ('wrong_model', 'Different response model')]:
        emit(CATEGORIES[8], label + ' reassigns same invocation once.', [changed(response_behavior=behavior, latency_ms=1), changed('w1', latency_ms=100)], {'worker_id': 'w1', 'dispatches': {'w0': 1, 'w1': 1}, 'main_state': 'COMPLETED', 'main_attempt': 2, 'job_count': 1}, 'reassignment', retry_policy=1)
    emit(CATEGORIES[8], 'Prospective zero retry bound prevents alternate dispatch.', [changed(response_behavior='disconnect'), w1], {'error': True, 'dispatches': {'w0': 1, 'w1': 0}, 'main_state': 'LOST_CONNECTION', 'main_attempt': 1}, 'reassignment', retry_policy=1, req={'retry_override': 0})
    emit(CATEGORIES[8], 'Failed worker is excluded rather than repeated.', [changed(response_behavior='disconnect')], {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'BLOCKED', 'main_attempt': 1}, 'reassignment', retry_policy=1)
    for behavior, label in [('disconnect', 'Actual socket disconnect'), ('http500', 'HTTP status failure'), ('malformed', 'Malformed JSON bytes'), ('array', 'Non-object response')]:
        emit(CATEGORIES[9], label, [changed(response_behavior=behavior)], {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'LOST_CONNECTION'})
    emit(CATEGORIES[9], 'Original transport timeout rejects unreturned result.', [w0], {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'LOST_CONNECTION'}, 'timeout')
    emit(CATEGORIES[9], 'Manual health refresh recovers new work without replay.', [changed(response_behavior='disconnect')], {'dispatches': {'w0': 2}, 'completed_results': 1, 'prior_state': 'LOST_CONNECTION', 'main_state': 'COMPLETED', 'job_count': 2}, 'reconnect')
    for behavior, label, completed in [('complete', 'Checked forty percent matches source', True), ('wrong_value', 'Wrong arithmetic rejected', False), ('invalid_report', 'Invalid report schema rejected', False), ('wrong_source', 'Unknown source rejected', False), ('string_value', 'Wrong numeric type rejected', False), ('truncated', 'Truncated transport result rejected', False)]:
        emit(CATEGORIES[10], label, [changed(response_behavior=behavior)], {'workflow_status': 'completed' if completed else 'blocked', 'writes': 1 if completed else 0, 'main_state': 'VERIFIED' if completed else 'LOST_CONNECTION' if behavior == 'truncated' else 'FAILED'}, 'workflow_verification')
    extras = [('cancel_before', 'Cancel before dispatcher entry', {'error': True, 'dispatches': {'w0': 0}, 'main_state': 'CANCELLED'}), ('cancel_running', 'Cancel after actual HTTP dispatch', {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'CANCELLED'}), ('revoke_worker', 'Protected worker disabled at admission', {'error': True, 'dispatches': {'w0': 0}, 'main_state': 'BLOCKED'}), ('revoke_categories', 'Protected categories withdrawn at admission', {'error': True, 'dispatches': {'w0': 0}, 'main_state': 'BLOCKED'}), ('change_model', 'Protected model changes at admission', {'error': True, 'dispatches': {'w0': 0}, 'main_state': 'BLOCKED'}), ('resources_down', 'Resource capacity withdrawn at admission', {'error': True, 'dispatches': {'w0': 0}, 'main_state': 'BLOCKED'}), ('revoke_after', 'Authority withdrawn after response dispatch', {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'BLOCKED'}), ('runtime_after', 'Runtime changes after response dispatch', {'error': True, 'dispatches': {'w0': 1}, 'main_state': 'BLOCKED'})]
    for control, label, expected in extras:
        emit('supplemental_controls', label, [w0], expected, control=control)
    emit('supplemental_controls', 'Owned restart marks prior unverified delivery lost.', [w0], {'prior_state': 'LOST_CONNECTION', 'completed_results': 2, 'job_count': 2, 'dispatches': {'w0': 2}}, 'scheduler_restart')
    for behavior, expected in [('context_complete', True), ('context_underfilled', False), ('context_wrong', False), ('context_truncated', False)]:
        emit('supplemental_controls', 'Strata controlled context protocol ' + behavior, [changed(protocol='strata_openai', response_behavior=behavior, verified_context=None)], {'context_passed': expected, 'dispatches': {'w0': 1}}, 'context_probe', target_tokens=1024)
    return ({'version': 1, 'cases': cases}, {'version': 1, 'oracles': oracles})

def seal(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path = Path(path)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError('Prospective corpus is already sealed.')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
if __name__ == '__main__':
    cases, oracles = build()
    print(json.dumps({'cases': len(cases['cases']), 'inputs_sha256': seal('evals/compute/campaign6_development.json', cases), 'oracles_sha256': seal('evals/compute/campaign6_development_oracles.json', oracles)}, indent=2))

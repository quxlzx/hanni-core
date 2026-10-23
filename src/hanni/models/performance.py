"""Bounded numeric observations; unknown metrics never become estimates."""
from __future__ import annotations

import math


def server_rates(payload):
    """llama.cpp rates describe server phases, not network or first-token time."""
    timings = payload.get('timings') if isinstance(payload, dict) else None
    timings = timings if isinstance(timings, dict) else {}
    result = {}
    for target, source in (('prompt_tps', 'prompt_per_second'),
                           ('generation_tps', 'predicted_per_second')):
        value = timings.get(source)
        if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10**9:
            result[target] = value
    return result


def percentile(values, quantile):
    """Nearest-rank percentile, with the convention explicit and reproducible."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def recent_performance(samples, now, *, window_seconds=3600):
    rows = [row for row in samples if 0 <= now - row['created_at'] <= window_seconds]
    rows = sorted(rows, key=lambda row: row['created_at'])[-100:]
    latency = [row['latency_ms'] for row in rows]
    def latest(field):
        return next((row.get(field) for row in reversed(rows) if row.get(field) is not None), None)
    return {'sample_count': len(rows), 'recent_failures': sum(row['error'] for row in rows),
        'window_seconds': window_seconds, 'last_latency_ms': latency[-1] if latency else None,
        'p50_latency_ms': percentile(latency, .5), 'p95_latency_ms': percentile(latency, .95),
        'ttft_ms': latest('ttft_ms'), 'generation_tps': latest('generation_tps'),
        'prompt_tps': latest('prompt_tps'), 'queue_ms': latest('queue_ms'),
        'ttft_kind': 'client_observed_first_content', 'rates_kind': 'server_reported_phase_rates',
        'percentile_method': 'nearest_rank',
        'history': [{'sampled_at': row['created_at'], **{field: row.get(field) for field in
                    ('latency_ms', 'ttft_ms', 'generation_tps', 'prompt_tps', 'queue_ms', 'error')}}
                    for row in rows[-32:]]}

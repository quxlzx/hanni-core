"""Pure synthetic inference cancellation; no lifecycle or task execution."""
import json
from pathlib import Path
import threading
import time
import argparse

from hanni.compute.registry import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from hanni.config.loader import load_config
from hanni.models.client import LlamaCppClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/phase3/cancellation-live.json'))
    args = parser.parse_args()
    config = load_config(Path('config'), env={})
    registry = ComputeRegistry(config.paths.data_dir)
    transport = InferenceTransport(registry, relay_only=True)
    worker = registry.worker('wonyoung-strata')
    result = {'scope': 'LIVE_PURE_INFERENCE_ONLY', 'upstream_abort': 'NOT PROVEN',
              'workflow_concurrency': 'NOT TESTED', 'actions': 0}
    if not registry.enabled or not worker['enabled'] or 'synthetic' not in worker['allowed_categories']:
        raise RuntimeError('Synthetic authorization unavailable')
    resources = transport.resources(worker)
    if not resources or resources.get('ram_available_bytes', 0) < 2 * 1024**3 or resources.get('vram_free_bytes', 0) < 256 * 1024**2:
        raise RuntimeError('Fresh resource reserves unavailable')
    health = transport.request(worker, 'GET', '/v1/models', timeout=5)
    if worker['model_id'] not in [row.get('id') for row in health.get('data', [])]:
        raise RuntimeError('Unexpected endpoint identity')
    cancel = threading.Event()
    started = time.perf_counter()

    def background():
        try:
            transport.request(worker, 'POST', '/v1/chat/completions', timeout=15, cancel=cancel,
                payload={'model': worker['model_id'], 'messages': [{'role': 'user', 'content':
                    'Write a numbered list of 80 fictional public star names. This is a synthetic test.'}],
                    'max_tokens': 384, 'temperature': 0, 'stream': False,
                    'chat_template_kwargs': {'enable_thinking': False}})
            result['background_outcome'] = 'RESPONSE_RETURNED'
        except Exception as exc:
            result['background_outcome'] = type(exc).__name__
            result['background_error'] = str(exc) if not isinstance(exc, TimeoutError) else 'Owned helper drain timed out'
        result['background_duration_ms'] = (time.perf_counter() - started) * 1000

    thread = threading.Thread(target=background)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with transport.lock:
                active = any(entry[0] == worker['worker_id'] for entry in transport.clients.values())
            if active or not thread.is_alive():
                break
            time.sleep(.02)
        result['owned_relay_boundary_reached'] = active
        client = LlamaCppClient(config.models.supervisor, max_attempts=1)
        began = time.perf_counter()
        answer = client.chat([{'role': 'user', 'content': 'What is 3 plus 4? Answer briefly.'}])
        result['resident_duration_ms'] = (time.perf_counter() - began) * 1000
        result['resident_response'] = str(answer)
        result['background_active_at_cancel'] = thread.is_alive()
    finally:
        began = time.perf_counter()
        cancel.set()
        transport.cancel(worker['worker_id'], cancel)
        thread.join(timeout=20)
        result['cancel_join_ms'] = (time.perf_counter() - began) * 1000
        result['owned_worker_finished'] = not thread.is_alive()
        with transport.lock:
            result['owned_handles_remaining'] = len(transport.clients)
        args.output.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

"""Queue ordering remains FIFO when the platform clock has tied readings."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
from hanni.compute import ComputeRegistry, ComputeScheduler

def test_same_clock_timestamp_preserves_admission_order(tmp_path):
    folder = tmp_path / 'compute'
    folder.mkdir()
    worker = {'worker_id': 'clock_fixture', 'node_id': 'local', 'local_url': 'http://127.0.0.1:43123', 'model_id': 'fixture', 'enabled': True, 'allowed_categories': ['synthetic'], 'capabilities': ['analysis'], 'concurrency': 1}
    (folder / 'deployment.json').write_text(json.dumps({'version': 1, 'enabled': True, 'nodes': [], 'workers': [worker], 'policy': {'timeout_seconds': 3}}))
    registry = ComputeRegistry(tmp_path, clock=lambda: 1000)
    registry.observe('clock_fixture', status='healthy', model_id='fixture', last_heartbeat=1000, max_context_verified=8192, context_reported=8192)
    entered, release = (threading.Event(), threading.Event())
    dispatches = []

    class Transport:

        def request(self, worker, method, path, *, payload, **_):
            marker = payload['messages'][-1]['content']
            dispatches.append(marker)
            if marker == 'occupier':
                entered.set()
                assert release.wait(3)
            return {'model': 'fixture', 'choices': [{'message': {'content': marker}, 'finish_reason': 'stop'}]}

        def close(self):
            pass
    scheduler = ComputeScheduler(registry, transport=Transport(), clock=lambda: 1000)

    def call(marker):
        return scheduler.chat([{'role': 'user', 'content': marker}], workflow_id='fixture', step_id=marker, invocation_id=marker, categories=['synthetic'], max_tokens=32)

    def await_queue(count):
        deadline = time.monotonic() + 2
        while len(scheduler.waiting) < count and time.monotonic() < deadline:
            time.sleep(0.001)
        assert len(scheduler.waiting) == count
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            occupied = pool.submit(call, 'occupier')
            assert entered.wait(2)
            older = pool.submit(call, 'older')
            await_queue(1)
            younger = pool.submit(call, 'younger')
            await_queue(2)
            release.set()
            assert occupied.result(3)[0] == 'occupier'
            assert older.result(3)[0] == 'older' and younger.result(3)[0] == 'younger'
            assert dispatches == ['occupier', 'older', 'younger']
            assert not scheduler.waiting and (not scheduler.queued)
    finally:
        release.set()
        scheduler.close()

"""Public isolated timing attribution, never actual-model/native/holdout evaluation.

Original returns, routing, registry definitions and permission/evidence oracles
are unchanged. Transparent instance-method timers and Python handler profiling
add measurement overhead. Results are inclusive overlapping wall intervals.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v3_review.service_fixture import ServiceFixture, QueuedStructuredClient
from scripts.v3_review.fixtures import fixture_facts
from scripts.v3_review.check_browser import runtime_manifest

spec = importlib.util.spec_from_file_location('public_workflow_engineering_helpers', ROOT / 'tests/integration/test_workflow_service_verifier.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


class Timings:
    def __init__(self):
        self.rows, self.lock, self.local = [], threading.Lock(), threading.local()
        self.enabled = True
        self.handler_codes = {}

    def add(self, metric, started, **extra):
        duration = (time.perf_counter_ns() - started) / 1e6
        if self.enabled:
            with self.lock:
                self.rows.append({'metric': metric, 'ms': duration, **extra})

    def wrap(self, obj, attribute, metric):
        original = getattr(obj, attribute)
        def timed(*args, **kwargs):
            started = time.perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                self.add(metric, started)
        setattr(obj, attribute, timed)

    def profile(self, frame, event, _arg):
        metric = self.handler_codes.get(frame.f_code)
        if metric and self.enabled:
            pending = getattr(self.local, 'handler_frames', None)
            if pending is None:
                pending = self.local.handler_frames = {}
            if event == 'call':
                pending[id(frame)] = time.perf_counter_ns()
            elif event == 'return' and id(frame) in pending:
                self.add(metric, pending.pop(id(frame)))

    def instrument(self, fixture):
        self.wrap(fixture.host, 'route', 'capability_route_inclusive')
        self.wrap(fixture.host, 'call', 'host_dispatch_inclusive')
        self.wrap(fixture.registry, 'execute', 'registry_execute_inclusive')
        self.wrap(fixture.client, 'chat', 'scripted_client_serialization')
        self.wrap(fixture.service, '_plan', 'planning_pipeline_inclusive')
        for method in ('begin_invocation', 'finish_invocation', 'recover'):
            self.wrap(fixture.service.store, method, 'store_' + method + '_inclusive')
        self.wrap(fixture.service.store, '_checkpoint', 'checkpoint_insert_without_commit')
        original = fixture.service.store.transaction
        @contextmanager
        def transaction():
            depth = getattr(self.local, 'transaction_depth', 0)
            self.local.transaction_depth = depth + 1
            started, body_end, entered = time.perf_counter_ns(), None, None
            try:
                with original() as db:
                    entered = time.perf_counter_ns()
                    if depth == 0:
                        self.add('transaction_outer_enter_lock_connect_begin', started)
                    try:
                        yield db
                    finally:
                        body_end = time.perf_counter_ns()
            finally:
                self.local.transaction_depth = depth
                self.add('transaction_outer_inclusive' if depth == 0 else 'transaction_nested_inclusive', started)
                if depth == 0 and body_end is not None:
                    self.add('transaction_outer_exit_commit_cleanup', body_end)
        fixture.service.store.transaction = transaction
        for name in ('file.read', 'file.write', 'file.stat'):
            self.handler_codes[fixture.registry.get(name).handler.__code__] = 'original_handler_' + name


def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0, 'measured': False}
    return {'n': len(values), 'p50_ms': statistics.median(values),
            'p95_ms': values[math.ceil(.95 * len(values)) - 1],
            'mean_ms': statistics.mean(values), 'min_ms': values[0], 'max_ms': values[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=10)
    args = parser.parse_args()
    if not 3 <= args.repeats <= 20:
        parser.error('repeats must be 3..20')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'passed': False, 'client_mode': 'scripted', 'disclosure': __doc__,
              'cases': [], 'recovery': [], 'errors': [], 'runtime_before': runtime_manifest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    timings = Timings()
    previous_main, previous_threads = sys.getprofile(), threading.getprofile()
    try:
        with tempfile.TemporaryDirectory(prefix='hanni-public-performance-') as temporary:
            directory = Path(temporary)
            facts = fixture_facts(directory / 'inputs')
            client = QueuedStructuredClient()
            fixture = ServiceFixture(directory / 'run', client=client)
            timings.instrument(fixture)
            sys.setprofile(timings.profile)
            threading.setprofile(timings.profile)
            timings.enabled = False
            fixture.start()  # Setup/database initialization/claim/thread startup excluded.
            try:
                for kind in ('read', 'artifact', 'analysis_artifact'):
                    for iteration in range(args.repeats + 1):
                        timings.enabled = iteration > 0
                        if kind == 'read':
                            helpers.queue_plan(client, [helpers.read_step('read', facts['source'], expected=facts['source'].read_text())],
                                               [helpers.row('read', 'file.read', path=str(facts['source']))])
                            goal = 'Read the text file ' + str(facts['source'])
                        elif kind == 'artifact':
                            helpers.artifact_plan(client, facts['source'])
                            goal = 'Read the text file ' + str(facts['source']) + ' and preserve its verified contents.'
                        else:
                            helpers.numeric_plan(client, facts['valid'])
                            goal = 'Compare both observed runs, compute pass percentages and their improvement, and save the report.'
                        started = time.perf_counter_ns()
                        key = fixture.submit(goal)
                        detail = helpers.drive_reviewed(fixture, key)
                        elapsed = (time.perf_counter_ns() - started) / 1e6
                        assert detail['status'] == 'completed', detail['status']
                        if kind == 'read':
                            assert detail['steps'][0]['result']['data']['text'] == facts['source'].read_text()
                        elif kind == 'artifact':
                            assert helpers.artifact_path(detail).read_text() == facts['source'].read_text()
                        else:
                            assert [item['value'] for item in detail['steps'][1]['result']['data']['report']['observations']] == [60, 90]
                            assert json.loads(helpers.artifact_path(detail).read_text())['observations'][0]['value'] == 30
                        if iteration:
                            result['cases'].append({'kind': kind, 'iteration': iteration, 'submission_to_terminal_ms': elapsed,
                                'verified_steps': detail['counts']['verified'], 'invocations': len(detail['invocations']),
                                'checkpoints': len(detail['checkpoints']), 'independent_outcome': True})
                timings.enabled = False
            finally:
                fixture.close()
        result['passed'] = True
    except BaseException as error:
        result['errors'].append(f'{type(error).__name__}: {error}')
    finally:
        sys.setprofile(previous_main)
        threading.setprofile(previous_threads)
        result['runtime_after'] = runtime_manifest()
        result['passed'] = result['passed'] and result['runtime_before']['sha256'] == result['runtime_after']['sha256']
        result['timings'] = timings.rows
        metrics = sorted({row['metric'] for row in timings.rows})
        result['summary'] = {metric: distribution([row['ms'] for row in timings.rows if row['metric'] == metric]) for metric in metrics}
        result['workflow_summary'] = {kind: distribution([row['submission_to_terminal_ms'] for row in result['cases'] if row['kind'] == kind])
                                      for kind in ('read', 'artifact', 'analysis_artifact')}
        result['recovery_summary'] = distribution([row['start_to_safe_projection_ms'] for row in result['recovery']])
        (output / 'performance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'cases': len(result['cases']), 'recoveries': len(result['recovery']), 'errors': result['errors']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

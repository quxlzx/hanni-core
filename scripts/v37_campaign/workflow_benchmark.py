"""Real GPU analysis through original WorkflowService; disclosed planner fixture."""
import json
import argparse
from dataclasses import replace
from pathlib import Path
import psutil
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.mcp.host import McpHost
from hanni.tools.registry import build_default_registry
from hanni.workflows import WorkflowService, WorkflowLimits
from tests.helpers import write_config_dir
from tests.integration.test_compute_v37_verifier import IndependentParallelPlan
from tests.unit.test_workflow_service import operation, approve_start


class ExplicitAnalysisPlan(IndependentParallelPlan):
    def chat(self, messages, **options):
        text = super().chat(messages, **options)
        if self.calls == 1:
            plan = json.loads(text)
            for step in plan['steps']:
                if step['kind'] == 'analysis':
                    step['description'] = ('Return exactly one factual percentage observation for passed divided by total, '
                        'multiplied by 100. Cite read at /data/text with JSON paths /passed and /total. '
                        'Do not add other observations or prose. Compute the value from the source.')
            text = json.dumps(plan)
        return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycle', choices=['cycle2', 'cycle3', 'cycle4'], default='cycle2')
    parser.add_argument('--analyses', type=int, choices=[2, 3], default=2)
    parser.add_argument('--output', type=Path, help='New private campaign directory for a reproducible repeat.')
    args = parser.parse_args()
    output = (args.output or ROOT / 'data/v37-manager/workflow-benchmark' / args.cycle).resolve()
    if not output.is_relative_to((ROOT / 'data/v37-manager').resolve()) or output.exists():
        raise SystemExit('Choose a new protected --output directory under data/v37-manager; prior results are preserved.')
    output.mkdir(parents=True, exist_ok=False)
    state = ROOT / 'data/v37-manager/preview/state'
    config = load_config(write_config_dir(output / 'config'), data_dir=state, env={})
    source = output / 'synthetic-benchmark.json'
    source.write_text('{"passed":9,"total":10}', encoding='utf-8')
    deployment = json.loads((ROOT / 'data/compute/deployment.json').read_text(encoding='utf-8'))
    for worker in deployment['workers']:
        worker['allowed_categories'] = ['synthetic', 'project', 'conversation']
    (state / 'compute/deployment.json').write_text(json.dumps(deployment), encoding='utf-8')
    shutil.copyfile(ROOT / 'data/compute/context-measurements.json', state / 'compute/context-measurements.json')
    registry = ComputeRegistry(state)
    compute = ComputeScheduler(registry)
    compute.start_monitor()
    request = compute.transport.request
    def observed_request(worker, method, path, **options):
        result = request(worker, method, path, **options)
        if method == 'POST' and path == '/v1/chat/completions':
            path = output / ('response-' + worker['worker_id'] + '-' + str(time.time_ns()) + '.json')
            path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    compute.transport.request = observed_request
    original_registry = build_default_registry(config)
    host = McpHost(original_registry, read_only=True)
    service = WorkflowService(state, limits=replace(WorkflowLimits(), step_timeout_seconds=180),
                              protected_roots=(output / 'config',))
    def resource_probe():
        ram = psutil.virtual_memory().percent
        return {'allowed': ram < config.models.critical_ram_percent, 'ram_percent': ram, 'gpu': None}
    service.attach(original_registry, ExplicitAnalysisPlan(str(source), args.analyses), host=host,
                   resource_probe=resource_probe, compute_scheduler=compute)
    service.start()
    records = []
    try:
        for mode in ('sequential', 'parallel'):
            service.client = ExplicitAnalysisPlan(str(source), args.analyses)
            workers = registry.workers()
            if args.analyses == 3:
                assert len(workers) == 3, 'Three independently verified workers are required.'
                service.limits = replace(service.limits, max_parallel_reads=1 if mode == 'sequential' else 3)
            elif mode == 'sequential':
                registry.configure_worker(workers[1]['worker_id'], enabled=False)
            else:
                registry.configure_worker(workers[1]['worker_id'], enabled=True)
            compute.refresh()
            key = operation(service, 'goal.submit', {'goal': 'Read JSON from ' + str(source) +
                f' and perform {args.analyses} independent checked percentage analyses.', 'mode': 'assisted'})['workflow_id']
            reviewed = service.wait(key, timeout=15)
            began = time.monotonic()
            approve_start(service, key, reviewed)
            final = service.wait(key, timeout=240)
            elapsed = time.monotonic() - began
            jobs = registry.jobs(key)
            record = {'mode': mode, 'duration_seconds': elapsed, 'workflow_id': key,
                'status': final['status'], 'counts': final['counts'], 'jobs': jobs,
                'planner': 'disclosed synthetic plan fixture, validated by original planner/permissions',
                'analysis': 'actual installed model inference; original evidence verification',
                'analyses': args.analyses,
                'placement': 'Same enabled workers in both modes; original scheduler chooses assignment.'}
            record['campaign_step_timeout_seconds'] = 180
            records.append(record)
            (output / 'results.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
            print(json.dumps({'mode': mode, 'status': final['status'], 'seconds': round(elapsed,3),
                'verified_jobs': sum(job['state']=='VERIFIED' for job in jobs),
                'workers': [job['worker_id'] for job in jobs]}), flush=True)
            if final['status'] != 'completed':
                break
    finally:
        service.close()
        compute.close()


if __name__ == '__main__':
    main()

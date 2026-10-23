"""Actual configured controller inference over prospective isolated Core inputs."""
from contextlib import ExitStack
from dataclasses import replace
import argparse
import json
from pathlib import Path
import time
from unittest.mock import patch
from hanni.config.loader import load_config
from hanni.models.client import LlamaCppClient, ModelUnavailableError
from hanni.models.adaptive import AdaptiveModelEngine
from hanni.models.adaptive import install as install_adaptive, uninstall as uninstall_adaptive
from hanni.models.manager import ModelManager, current, install
from scripts.campaign10_core.harness import run_case, original_session, normalize_case, substitute, attach_dashboard_facades
from scripts.campaign10_manager.isolation import validate_dispatch
from scripts.campaign10_manager.model import ModelBudget
ROOT = Path(__file__).resolve().parents[2]

def actual_config(root):
    config = load_config(ROOT / 'config', data_dir=Path(root), env={})
    spec = replace(config.models.supervisor, max_tokens=256, temperature=0, top_p=1, request_timeout_seconds=45)
    return replace(config, models=replace(config.models, models=(spec,)))

def execute_case(case, root, budget):
    case = normalize_case(case)
    root = Path(root).resolve()
    config = actual_config(root)
    prompts = [substitute(turn['prompt'], root, {}) for turn in case.get('user_turns', [])] or [substitute(case['query'], root, {})]
    budget.begin(case['id'], prompts)
    posts_start = len(budget.wire)
    started = time.perf_counter()

    def no_launch(*args, **kwargs):
        raise ModelUnavailableError('Campaign reuses only the verified existing server.')
    with ExitStack() as stack:
        previous = current()
        manager = ModelManager(config, launch=no_launch, stop=no_launch)
        install(manager)
        stack.callback(install, previous)
        stack.callback(manager.close)
        engine = AdaptiveModelEngine(config, compute_scheduler=None)
        stack.callback(engine.close)
        install_adaptive(engine)
        stack.callback(uninstall_adaptive, engine)
        client = engine.wrap_client(LlamaCppClient(config.models.supervisor, max_attempts=1))
        calls = []

        def factory(state):
            attach_dashboard_facades(state)
            state.controller_telemetry.start()
            sampling_started = time.monotonic()
            sample_deadline = sampling_started + 10
            while state.controller_telemetry.snapshot().get('sampled_at') is None and time.monotonic() < sample_deadline:
                time.sleep(0.05)
            original_execute = state.registry.execute

            def observed(request):
                row = {'name': request.name, 'arguments': dict(request.arguments), 'confirmed': request.confirmed, 'actor_profile': request.actor_profile}
                calls.append(row)
                try:
                    validate_dispatch(state, request, root)
                    result = original_execute(request)
                    row['result'] = result.to_dict()
                    return result
                except Exception as exc:
                    row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
                    raise
            stack.enter_context(patch.object(state.registry, 'execute', observed))
            session = original_session(state, client)
            sample = state.controller_telemetry.snapshot()
            state.session_metadata['workflow_telemetry_warmup'] = {'elapsed_ms': (time.monotonic() - sampling_started) * 1000, 'maximum_seconds': 10, 'sample_observed': sample.get('sampled_at') is not None, 'original_error': sample.get('error')}
            return session
        result = run_case(case, root, config=config, session_factory=factory, connection_authorizer=lambda address: address == ('127.0.0.1', 8080), model_counter=lambda: budget.task_posts, on_prepared_turns=lambda task_id, turns: budget.begin(task_id, [t['prompt'] for t in turns]))
        result['routing'] = engine.snapshot()
        result['actual_registry_calls'] = calls
        result['generation_wire_indices'] = list(range(posts_start, len(budget.wire)))
        result['actual_model_calls'] = budget.task_posts
        result['duration_ms'] = (time.perf_counter() - started) * 1000
        result['evidence_categories'] = ['LIVE_MODEL_ISOLATED_SERVICES'] if budget.task_posts else ['ISOLATED_IMPLEMENTATION']
        if result.get('inert_mcp_provider_calls'):
            result['evidence_categories'].append('MOCK_DEPENDENCY')
        if calls and all((row['name'] in {'system.stats', 'system.performance', 'process.top_memory', 'process.list', 'process.inspect', 'system.cpu', 'system.memory', 'system.battery', 'system.disk_usage'} for row in calls)):
            result['evidence_categories'].append('LIVE_READ_ONLY')
        result['request_path_original'] = True
        result['mock_model'] = False
        return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve all earlier inference attempts.')
    args.output.mkdir(parents=True)
    text = args.inputs.read_text(encoding='utf8')
    cases = json.loads(text) if args.inputs.suffix == '.json' else [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(cases, dict):
        cases = cases['cases']
    if args.limit:
        cases = cases[:args.limit]
    budget = ModelBudget(args.output / 'model')
    summaries = []
    with budget.transport():
        for index, case in enumerate(cases, 1):
            root = args.output / f'case-{index:03d}'
            try:
                row = execute_case(case, root, budget)
            except Exception as exc:
                row = {'id': case['id'], 'evidence_categories': ['NOT_RUN'], 'error': {'type': type(exc).__name__, 'message': str(exc)}, 'actual_model_calls': budget.task_posts}
            (args.output / f'receipt-{index:03d}.json').write_text(json.dumps(row, indent=2, default=str) + '\n', encoding='utf8')
            budget.save()
            summary = {k: row.get(k) for k in ('id', 'actual_model_calls', 'actual_generated', 'duration_ms', 'error')}
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
    (args.output / 'SUMMARY.json').write_text(json.dumps({'tasks': len(cases), 'actual_generation_posts': len(budget.wire), 'rows': summaries}, indent=2) + '\n', encoding='utf8')
if __name__ == '__main__':
    main()

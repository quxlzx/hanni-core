"""Real fixed/default vs adaptive comparison on a sealed synthetic holdout."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).parent)]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
from hanni.models.client import LlamaCppClient
from hanni.workflows.verification import parse_evidence_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--capabilities', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--context', type=Path)
    p.add_argument('--identity-prepared', type=Path)
    args = p.parse_args()
    campaign, output = args.campaign.resolve(), args.output.resolve()
    if not output.is_relative_to((ROOT / 'data/v40-verification').resolve()) or output.exists():
        raise SystemExit('New protected verifier evidence required.')
    output.mkdir(parents=True)
    encoded = (campaign / 'protocol.json').read_bytes()
    digest = hashlib.sha256(encoded).hexdigest()
    assert digest == (campaign / 'protocol.sha256').read_text().strip()
    protocol = json.loads(encoded)
    baseline = [json.loads(x) for x in (campaign / 'baseline-results.jsonl').read_text().splitlines()]
    cap_bytes = args.capabilities.read_bytes()
    cap_rows = json.loads(cap_bytes)
    config = load_config(ROOT / 'config', env={})
    registry = ComputeRegistry(ROOT / 'data')
    compute = ComputeScheduler(registry)
    engine = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=output / 'state')
    raw = LlamaCppClient(config.models.supervisor, max_attempts=1)
    adapter = engine.wrap_client(raw)
    rows = []
    try:
        if args.identity_prepared:
            prepared = args.identity_prepared.resolve()
            assert prepared.is_relative_to((ROOT / 'data/v40-verification').resolve())
            cache = json.loads((prepared / 'runtime-file-cache.json').read_text())
            compute.transport.identity_file_cache = {ast.literal_eval(k): v for k, v in cache.items()}
            files = json.loads((prepared / 'identity-files.json').read_text())
            engine.register_identity_files('worker:wonyoung-strata', model_files=files['model_files'],
                backend_files=files['backend_files'], evidence_sha256=hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                environment='independent registered existing model/backend full-SHA cache, stat rechecked before inference')
        engine.refresh()
        if args.context:
            context_rows = json.loads((args.context / 'results.json').read_text())
        else:
            context_rows = []
        for endpoint in ['local:supervisor', 'worker:athena-p40', 'worker:athena-p6000', 'worker:wonyoung-strata']:
            probes = [r for r in cap_rows if r['endpoint_id'] == endpoint and r.get('passed')]
            capabilities = ['text'] + [r['kind'] for r in probes if r['kind'] in {'structured_json', 'tool_calling'}]
            context = next((r for r in probes if r['kind'] == 'long_context'), None)
            if endpoint.startswith('worker:') and context_rows:
                context = next((r for r in context_rows if 'worker:' + r['worker_id'] == endpoint and r['passed']), None)
            engine.record_capability_evidence(endpoint, identity=engine.endpoint_identity(endpoint),
                capabilities=capabilities, evidence_sha256=hashlib.sha256(cap_bytes).hexdigest(),
                environment='real isolated synthetic probes; temp0 thinkingoff',
                metadata={'structured_output_formats': ['json_object'], 'tool_calling_formats': ['openai_function']},
                **({'context_tokens': context['target_tokens'], 'observed_prompt_tokens': context['observed_prompt_tokens'],
                    'retrieval_passed': True} if context else {}))
        # Development-only measured inputs. Holdout results remain out of policy profiles until all decisions are sealed.
        for row in baseline:
            if row['split'] != 'development':
                continue
            engine.record_evaluation(row['endpoint_id'], identity=engine.endpoint_identity(row['endpoint_id']),
                task_category=row['category'], correct=row['grading']['passed'], verified_success=row['grading']['passed'],
                latency_ms=row['latency_ms'], evidence_sha256=hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
                environment='prospective synthetic development; temp0 thinkingoff output384',
                evaluation_id='v40-development:' + row['endpoint_id'] + ':' + row['case_id'])
        (output / 'selector-input.json').write_text(json.dumps(engine.snapshot(), indent=2), encoding='utf8')
        # Passive refresh per case avoids stale health; no inference starts or model changes occur here.
        for case in protocol['cases']:
            if case['split'] != 'holdout':
                continue
            engine.refresh()
            request = ModelRequest(task_category=case['category'], privacy_categories=frozenset({'synthetic'}),
                capabilities=frozenset({'text'}), output_tokens=protocol['settings']['max_tokens'])
            messages = [{'role': 'system', 'content': protocol['system']}, {'role': 'user', 'content': case['prompt']}]
            def verified(value):
                try:
                    return parse_evidence_json(value) == case['expected']
                except Exception:
                    return False
            row = {'case_id': case['id'], 'category': case['category'], 'protocol_sha256': digest,
                   'synthetic_only': True, 'verification': 'exact same sealed oracle as baseline', 'passed': False}
            began = time.perf_counter()
            try:
                value = adapter.chat_verified(messages, request=request, validator=verified,
                    temperature=0, max_tokens=protocol['settings']['max_tokens'])
                row.update(passed=verified(value), response=value)
            except Exception as error:
                row.update(error_class=type(error).__name__)
            row['latency_ms'] = (time.perf_counter() - began) * 1000
            row['decision'] = engine.snapshot()['decisions'][0]
            rows.append(row)
            (output / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
            print(json.dumps({'case': case['id'], 'passed': row['passed'], 'milliseconds': round(row['latency_ms'], 1),
                              'endpoint': row['decision']['endpoint_id'], 'fallbacks': len(row['decision']['fallbacks'])}), flush=True)
        (output / 'selector-output.json').write_text(json.dumps(engine.snapshot(), indent=2), encoding='utf8')
    finally:
        engine.close()
        compute.close()


if __name__ == '__main__':
    main()

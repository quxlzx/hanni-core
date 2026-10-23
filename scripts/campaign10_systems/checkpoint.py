"""Public C10 report/checkpoint; only development and public historical queries."""
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
from .author import ROOT, DIMENSIONS
from .runner import source_manifest

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def normalized(value):
    return re.sub('\\s+', ' ', value.casefold()).strip()

def novelty():
    allowed = ['evals/memory/campaign3_development.jsonl', 'evals/workflows/campaign4_development.json', 'evals/workflows/campaign4_supplemental.json', 'evals/workflows/campaign4_explicit_goal_supplement.json', 'evals/voice/campaign7-development/references.json']
    queries = []

    def harvest(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {'expected', 'oracle', 'oracles', 'checks', 'results'}:
                    continue
                if key in {'query', 'goal', 'prompt', 'transcript'} and isinstance(child, str):
                    queries.append(normalized(child))
                elif isinstance(child, (dict, list)):
                    harvest(child)
        elif isinstance(value, list):
            for child in value:
                harvest(child)
    for name in allowed:
        path = ROOT / name
        if path.suffix == '.jsonl':
            for line in path.read_text(encoding='utf8').splitlines():
                if line.strip():
                    harvest(json.loads(line))
        else:
            harvest(json.loads(path.read_text(encoding='utf8')))
    inputs = [json.loads(line) for line in (ROOT / 'data/campaign10-systems/prospective-cycle1/inputs.jsonl').read_text(encoding='utf8').splitlines()]
    query_set = set(queries)
    near = []
    for row in inputs:
        query = normalized(row['user_turns'][0]['prompt'])
        match, ratio = max(((other, SequenceMatcher(None, query, other).ratio()) for other in query_set), key=lambda pair: pair[1])
        if ratio >= 0.8:
            near.append({'id': row['id'], 'similarity': round(ratio, 4), 'old_query_sha256': hashlib.sha256(match.encode()).hexdigest()})
    return {'scope': 'Normalized query-only comparison to explicitly listed PUBLIC development files; no historical/final oracle consulted.', 'files': {name: digest(ROOT / name) for name in allowed}, 'old_query_count': len(queries), 'old_unique_query_count': len(query_set), 'new_queries': len(inputs), 'exact_collisions': [row['id'] for row in inputs if normalized(row['user_turns'][0]['prompt']) in query_set], 'near_at_0_8': near, 'manual_diversity': 'New objectives vary durable state, dependencies, authority, source identity, privacy, continuation, format, and failure timing; not name/number substitutions.'}

def publish():
    report_root = ROOT / 'docs/campaign10'
    report_root.mkdir(parents=True, exist_ok=True)
    baseline_path = ROOT / 'data/campaign10-systems/development-cycle1/GRADES.json'
    retake_path = ROOT / 'data/campaign10-systems/development-workflow-schema-cycle2/GRADES.json'
    baseline = json.loads(baseline_path.read_text(encoding='utf8'))
    retake = json.loads(retake_path.read_text(encoding='utf8'))
    current = {row['id']: row for row in baseline['cases']}
    for row in retake['cases']:
        current[row['id']] = row
    rows = list(current.values())
    frozen = source_manifest()
    owned = {str(path.relative_to(ROOT)).replace('\\', '/'): digest(path) for path in (ROOT / 'scripts/campaign10_systems').glob('*.py')}
    owned['tests/test_campaign10_systems.py'] = digest(ROOT / 'tests/test_campaign10_systems.py')
    evidence = {'tasks': 60, 'baseline': {'path': str(baseline_path.relative_to(ROOT)), 'sha256': digest(baseline_path), 'counts': baseline['counts'], 'input_sha256': digest(ROOT / 'data/campaign10-systems/prospective-cycle1/inputs.jsonl')}, 'schema_retake': {'tasks': 12, 'path': str(retake_path.relative_to(ROOT)), 'sha256': digest(retake_path), 'counts': retake['counts'], 'oracle_objects_unchanged': True, 'amendment_sha256': digest(ROOT / 'data/campaign10-systems/prospective-workflow-schema-cycle2/AMENDMENT.json')}, 'current_per_task_projection': {'counts': dict(Counter((r['contract_verdict'] for r in rows))), 'scope': 'Transparent current per-task view uses corrected input only for12; original60 and retake12 remain separate cohorts.', 'dimensions': {d: dict(Counter((r['dimensions'][d]['status'] for r in rows))) for d in DIMENSIONS}, 'cases': rows}, 'novelty': novelty(), 'source': frozen, 'held_owned_helpers_tests': owned, 'production_edits': [], 'real_model_requests': 0, 'real_remote_requests': 0, 'physical_audio_calls': 0, 'model_intent_and_response_quality': 'NOT_MEASURED', 'private_final': 'VERIFIER_OWNED_NOT_ACCESSED', 'helper_tests': {'current': 'data/campaign10-systems/helper-contracts-cycle4.xml', 'pass': 13, 'historical_failed': 'data/campaign10-systems/helper-contracts-cycle1.xml', 'historical_pass': 7, 'historical_fail': 1}, 'independent_public': {name: digest(ROOT / name) for name in ('data/campaign10-verifier-public/development-system-reproductions/SUMMARY.json', 'data/campaign10-verifier-public/development-negative-reproductions/SUMMARY.json')}, 'replay_metric_erratum': {'path': 'data/campaign10-systems/REPLAY_METRIC_ERRATUM.json', 'sha256': digest(ROOT / 'data/campaign10-systems/REPLAY_METRIC_ERRATUM.json')}, 'source_ready': True, 'pending': ['Root-coordinated actual model/controller/native acceptance and untouched final.']}
    evidence_path = report_root / 'SYSTEMS_EVIDENCE.json'
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf8', newline='\n')
    abbreviations = {'PASS': 'P', 'FAIL': 'F', 'NOT_MEASURED': 'NM', 'BLOCKED': 'B', 'NOT_APPLICABLE': 'NA'}
    table = ['| Task | Family | Contract | Intent | Context | Tools | Args | Auth | Exec | Verify | Response | Latency | Recovery |', '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for row in rows:
        table.append('| ' + ' | '.join([row['id'], row['family'], row['contract_verdict'], *(abbreviations[row['dimensions'][d]['status']] for d in DIMENSIONS)]) + ' |')
    text = "# Campaign 10 Systems development review\n\nThe original60-task baseline is **47 PASS /13 FAIL**. A separately sealed, schema-only12-task correction is **9 PASS /3 FAIL**, with unchanged oracle objects. The transparent current per-task view is **56/60 controlled contracts**; it does not replace either denominator. All72 task executions used unchanged production source, zero real model requests, zero remote/provider calls and zero physical audio calls. No production repair was made.\n\nThe60 manually authored owner objectives span11 families:10 memory lifecycle/preferences,10 project continuation/identity,15 workflow reporting/recovery/authority,10 distributed scheduler scenarios,5 cluster observations,5 software/text voice cases and5 screen availability/admission cases. Difficulty was authored before execution:7 easy single observations,24 medium state/context combinations and29 hard authority, dependency, failure or epistemic boundaries. Expected outcomes and all ten dimension assignments were authored before routing or execution. Inputs and oracles are separate JSONL files. The executor dispatches on public operations, never case IDs, expected results or teacher responses.\n\nThe initial12 workflow failures were my authored input error: presence criteria omitted the original JSON Schema's required `expected:null`. The original planner correctly rejected those inputs before dispatch. A separate correction adds exactly14 null fields and preserves every original oracle object. The retained helper7/8 run also exposed a grader exception-variable bug; the final helper gate passes13 meaningful adapter/grading/schema-invariance/native-replay checks. A read-only replay metric erratum corrects the old helper's use of `verified` instead of the original invocation state `finished`; native step verification reanalysis of all27 retained workflow receipts changes no counts and reruns no task. These are harness findings, not HANNI security or model-quality failures.\n\nFour current prospective objectives remain unmatched: SYS020 removes an alias but the original resolver still matches the remaining ordinary project-name word; SYS021 supplies a literal generated-artifact read path where the original planner requires a typed predecessor path; SYS030 expects UNCERTAIN after a synchronous timeout-after-write, but the original handler returns a defined failed receipt and the workflow blocks; SYS032 expects cancellation after owner rejection, but the original state is BLOCKED. The latter three retain truthful failure, no replay and original authority. Their exact oracles remain failed; no result was promoted or permission changed. The independent verifier reproduced these four public boundaries plus positive five-step restart and uncertain-write control cases, and found no justified production repair.\n\nWorkflow inputs use the original WorkflowPlanner, WorkflowService, SQLite ledger, McpHost, registered file handlers and verification gates. Outline/binding responses and budget probes are controlled dependencies, so this is not real goal understanding. Completed long chains perform five native operations, persist checkpoints, recover an in-flight retry-safe hash through original service detach/reattach, and preserve earlier completed observations. This is service recovery, not an additional actual backend-process restart. Managed writes have original approval/dispatch authority and actual filesystem readbacks. Distributed cases use the original protected registry/scheduler and original `verify_context`, with explicitly MOCK token/retrieval transport results; they are not hardware context certificates or genuine inference. Setup calls and target calls are recorded separately, and all native scheduler slots/queues are released.\n\nProject context reads real disposable productivity and memory stores, including local deadline task state, owner notes, file links, scoped decisions and tentative plans. Memory correction/deletion/reopen and suggestion review use original APIs. Cluster refresh/snapshot uses original monitoring logic with mocked connectivity/telemetry and no SSH. Voice relevance is TEXT_ONLY; pre-stop and sample-rate guards use controlled device/decoder leaves without importing/loading ASR or VAD models. Physical microphone, wake, playback and interruption remain BLOCKED by the user's stated hardware unavailability. The original awareness projection says no screen pipeline/capture/context; the native multimodal adapter rejects image objects before model submission. Those screen contracts verify honest absence and do not constitute vision task completion.\n\nEvery task records intent, retrieved_context, tools, arguments, authorization, execution, outcome_verification, final_response, latency and recovery. P/F below means the specific prospective isolated contract only. NM means there is no measurement. All genuine model final-response quality is NM, and no controlled call count is a model-selection accuracy sample. Latency is bounded component elapsed time, not live inference or speech/capture-to-response performance.\n\nThe historical public baselines are unlike denominators: C3 memory Recall@5 remained44.68%/60.64% and project identification66.67%; C4 controlled development103/120 and independent32/40 included separate owned-process restart proof; C5's1800 attempts were blocked with no generation; C6 measured controlled scheduling69/79 and independent19/22 while live SSH required fresh authentication; C7 retained its logical speaking-before-playback limitation and had no ASR/physical speech or vision result; C8 measured actual native UI57/60 and visual8.7583 plus separate genuine conversations. These values are prior evidence, not current C10 passes or paired performance improvements.\n\nExecution: `.venv\\Scripts\\python.exe -X utf8 -m scripts.campaign10_systems.runner --inputs <sealed inputs.jsonl> --output <fresh campaign-owned output>`; grade separately with `scripts.campaign10_systems.grade --receipts ... --oracles ... --output ...`. Root may wrap an actual original controller using `runner.original_memory_wrapper`; no fixed answer is supplied, and the original registry/profile/emergency-stop/privacy gates remain. Actual model/controller/native acceptance and the untouched45-task final are root/verifier-coordinated and pending. Private final inputs/oracles were not accessed.\n\nRaw input seals, source byte archives, controlled planner replies, original result/verification/checkpoint traces, side-effect ledgers and readbacks are retained under `data/campaign10-systems`. Public hash/evidence metadata is in [SYSTEMS_EVIDENCE.json](SYSTEMS_EVIDENCE.json). Production and helper source is held after these checks.\n\n"
    (report_root / 'SYSTEMS_REVIEW.md').write_text(text + '\n'.join(table) + '\n', encoding='utf8', newline='\n')
    checkpoint = {'systems_evidence_sha256': digest(evidence_path), 'held_owned_helpers_tests': owned, 'source_manifest_sha256': hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(), 'production_edits': [], 'tasks': 60, 'baseline': baseline['counts'], 'schema_retake': retake['counts'], 'source_ready': True, 'model_requests': 0, 'private_final_accessed': False}
    path = ROOT / 'data/campaign10-systems/SOURCE_READY.json'
    path.write_text(json.dumps(checkpoint, indent=2) + '\n', encoding='utf8', newline='\n')
    return checkpoint
if __name__ == '__main__':
    print(json.dumps(publish(), indent=2))

# Campaign 5 development benchmark review

The prospective development corpus contains 200 synthetic tasks, with 20 in
each requested family. The inputs and deterministic reference oracles were
sealed before observing model responses. Implementation checks use controlled
fixtures and are separate from live model quality results.

## Prospective corpus

| Task family | Tasks | Native request category | Evidence scope |
| --- | ---: | --- | --- |
| Simple commands | 20 | conversation | Exact transformations of synthetic inputs |
| Tool selection | 20 | tool_selection | Textual recommendations using original registered schemas; no dispatch |
| Planning | 20 | planning | Dependency graphs, topological constraints and independently calculated timing |
| Coding | 20 | coding | Restricted pure Python with independently specified examples |
| Analytical reasoning | 20 | analysis | Arithmetic, probability and statistics |
| Long-context retrieval | 20 | long_context | Bounded ledgers of 24 to 62 records; not near-limit context validation |
| Structured output | 20 | structured_output | Strict JSON types, escaping, nesting and missing values |
| Memory-assisted questions | 20 | memory | Supplied synthetic source records; not production memory retrieval |
| Workflow reasoning | 20 | analysis | Supplied checkpoint evidence; not actual workflow execution |
| Complex multi-step analysis | 20 | analysis | Constrained selection with independent enumeration |

The default output limit is 256 tokens. Planning and coding use a prospectively
fixed 512-token limit. Every arm uses temperature zero and top_p one. Inputs do
not carry expected answers, private checker inputs or grader results.
Prospective difficulty labels comprise 20 easy, 55 normal and 125 hard tasks.
The largest serialized long-context message payload is 7,311 UTF-8 bytes; this
is a byte measurement, rather than measured model token capacity.

| Sealed artifact | SHA-256 |
| --- | --- |
| Development inputs | `d8482a92554913ab24f6836697d694bf61aae4ba80545cc933d0f6d6727a1951` |
| Development oracles | `4d53e4d60c019bf247013db990dd88376f4a6c852084a9f5f6b69979b12c832a` |
| Prospective author | `dba3089eec21fe49fee05a04e9d7309fb3493d4bf167028a8c54768739e5ee83` |

## Original inference boundary

The collection CLI uses the original AdaptiveModelEngine and protected compute
transport against campaign-owned configuration copies and SQLite databases.
This is a ModelLab-adjacent benchmark because the existing desktop ModelLab API
accepts its predefined suites, rather than this new corpus. No model service,
monitor, authentication change or resource guard bypass is introduced.

The dynamic configured inventory supplies individual pinned arms, plus native
adaptive placement and selective collaboration. Individual arms have no
fallback. Adaptive placement retains the existing fallback ceiling, with a
narrower prospective bound when supplied. Selective collaboration uses the
original automatic policy without answer-backed validation. Generation budget
reservations cover one individual request, all permitted adaptive attempts, or
all permitted collaboration participants and rounds before dispatch.

The observer retains actual synthetic request bodies and response bytes through
the original urllib/httpx calls. Authentication and headers are excluded. Server
aliases and finish reasons remain reported metadata, rather than weight identity
proof. Original tokens, resources and timing are retained when available. Missing
measurements remain null. Resource samples describe admission, not peak memory or
incremental hardware cost. Orchestration overhead is measured outside the actual
first-to-last HTTP envelope.

Optional native tool definitions and response formats are forwarded unchanged.
Timeout and fallback metadata are consumed as control bounds and never become
generation arguments. A requested deadline uses the original cancellation
checks; a local blocking read remains subject to the original transport timeout.
The deadline does not set a caller-owned cancellation event.

Final cases clone the complete immutable development profile SQLite checkpoint
separately for every case and mode, including quality, latency and collaboration
state. Original unscored telemetry writes stay in that clone. Final answers never
update profiles or select later final cases. No quality profile is fabricated
when development produced no actual responses.

## Controlled implementation checks

The focused suite passed 31 checks, exit zero:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_campaign5_benchmark_contracts.py -q --junitxml=data/campaign5-development/checker-contracts-cycle3.xml
```

Checks cover the sealed family denominators, original registered argument
validators, strict JSON and type boundaries, alternative valid dependency
orders, restricted coding execution, actual disposable coding child outcomes,
exact controlled HTTP bytes without credentials, input/oracle separation,
blocked null semantics, reported alias limits, honest declined collaboration,
per-case profile isolation, native control metadata, owned cancellation and
fallback/round budget reservations. The controlled HTTP service and fake
unavailable engines are unit fixtures, never live model results.

The Python checker permits a restricted AST and bounded child process, with
imports, file access, reflection, recursion and unbounded constructs rejected.
This limits accepted implementations; rejection does not establish that a
different unrestricted implementation would be mathematically wrong.

## Collection status

The manager owns live discovery and collection. Initial original admission found
the resident Qwen3.5-4B-Q4_K_M healthy but below the unchanged 2 GiB available-RAM
guard. All three remote workers were unreachable through their configured LAN
and Tailscale paths. The P40/P6000 configuration names Q4_K_S rather than the
requested IQ3_S variant; unavailable remote runtimes cannot confirm loaded
weights. These are environment observations, not benchmark answers.

The manager's original-native pilot completed one task in each of the six arms.
All six were blocked before generation, with zero actual generation requests,
no quarantine and unchanged source. Resident exclusions include insufficient
RAM reserve; remote exclusions include unverified context/capability, unhealthy
endpoints and unknown resources. Selective collaboration reported no authorized
eligible inference endpoint. These are observed admission outcomes, rather than
semantic model failures. Pilot evidence remains under
`data/campaign5-development/native-pilot-cycle1`.

The full collection finished on the frozen source, with 1,200 original-native
admission records: the same 200 sealed inputs in each of six arms. Every record
is `BLOCKED_NO_INFERENCE`. All six arms retained their complete task denominators;
there were zero actual generation HTTP requests, zero captured HTTP records,
zero returned model answers and no quarantine. Source and configuration hashes
were unchanged, and no owner service was started or stopped.

| Arm | Native attempts | Blocked | Actual generation requests | Measured semantic tasks |
| --- | ---: | ---: | ---: | ---: |
| Resident 4B supervisor | 200 | 200 | 0 | 0 |
| Athena P6000 | 200 | 200 | 0 | 0 |
| Athena P40 | 200 | 200 | 0 | 0 |
| Wonyoung Strata | 200 | 200 | 0 | 0 |
| Native adaptive | 200 | 200 | 0 | 0 |
| Native selective collaboration | 200 | 200 | 0 | 0 |
| Total | 1,200 | 1,200 | 0 | 0 |

Every arm contains 20 attempted tasks in each of the ten families. Therefore
each family retains 120 blocked attempts across the six arms. There are no
semantically measured family/model pairs. Accuracy and structured-task success
remain null with a zero measured-response denominator, rather than zero-percent
model quality or a passed development benchmark. Prompt/completion tokens,
generation latency P50/P95, actual-inference resource samples and orchestration
overhead likewise remain unmeasured.

The 1,000 original selection decision records from individual/adaptive modes
retain their endpoint exclusions. Selective collaboration stops at its native
eligibility boundary before generating a selection decision and retains the
original exception. Resident inventory snapshots show available RAM between
1,873,199,104 and 2,004,500,480 bytes, below the unchanged 2,147,483,648-byte
reserve. Snapshot values can repeat across cases; these are not 1,200 independent
hardware measurements. All three worker health states remain unhealthy, with
no verified context/capability/resource proof. Configured model labels do not
establish remote runtime identity.

Evidence is retained under
`data/campaign5-development/native-full-cycle1/arms/*/receipts.jsonl`, with
per-arm discovery, original final state, source hashes and aggregate summaries.
The manager independently accepted the structural/provenance audit. Native
development model-quality acceptance is blocked. Adaptive and collaboration
benefit remain unmeasured, and no default model replacement is justified.

The independent final input cohort uses strict admission without the legacy
supervisor fallback and includes native tool-call and structured-format cases.
Development permits the retained legacy supervisor path and evaluates textual
tool recommendations. Those eligibility and task-format differences must remain
visible; they cannot be treated as matched native tool quality measurements.
Development structured-output tasks grade JSON text; they do not establish
original API schema-format compliance. No development answers or quality
measurements were available for profile import. The manager froze the actual
closed adaptive-arm database as an empty development checkpoint, rather than
manufacturing comparisons, capabilities or context proofs.

The manager's final source manifest freezes 427 files with SHA-256
`10c73380215acfe307906da905daab58570eea5e7e9b7a53ca3938d66ff85e62`.
Only derived reports may change after this freeze. The independent hash-only
novelty check found zero normalized final-user-message collisions between the
public 200 development tasks and the private 100 final tasks, without disclosing
private inputs or answers.

## Frozen engineering sources

| Source | SHA-256 |
| --- | --- |
| `scripts/campaign5_benchmark/runner.py` | `20ca169d10d8764f10b9ac78ea0362b37836c234140e63405e4fd9cc3bb30a69` |
| `scripts/campaign5_benchmark/live.py` | `aceef47d45a602854c7c5abc930f698076e4265c2efa66dceeb108440f099aeb` |
| `scripts/campaign5_benchmark/checkers.py` | `390b2cf8f6dbb0decbd0ff214187de753130f2ed23df9ef649be38117401c0a6` |
| `tests/unit/test_campaign5_benchmark_contracts.py` | `10f3950ae51c11cad439ec244a6a3b013463b52074711f2b4cf52d3df3838f78` |

The prospective corpus and author remain unchanged. Future aggregate results
may update this report; tested source and sealed inputs remain frozen.

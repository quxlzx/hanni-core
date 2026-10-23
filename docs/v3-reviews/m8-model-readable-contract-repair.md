# Generic model-readable workflow contract repair

This implementation candidate follows failed public-cycle checkpoint `d0c87d2`. Public goals and outcome oracles were not changed by Worker1. No sealed inputs, evaluator, oracle or raw output were inspected or rerun, and no configured model or native app was started. Passing scripted engineering checks below does not establish real-model completion or unseen generalization.

The original planner referred to a supplied schema while sending it only as `response_format`. The matching [llama.cpp grammar documentation at commit 50f068fff](https://github.com/ggml-org/llama.cpp/blob/50f068fff/grammars/README.md#json-schemas--gbnf) explains that response schemas constrain generation without being inserted into the prompt. The model therefore needs an explicit readable contract independently of grammar enforcement.

The shared `schema_messages` helper now puts the full unchanged authoritative local JSON Schema in the trusted system message for OUTLINE, BINDING and REPORT. The existing low-complexity schema projection still serves generation transport. The original user JSON stays flat, with descriptions, goals, source results and capability metadata treated as quoted untrusted data. Input privacy checks remain active. A combined serialized-message byte bound includes instructions, full schema and data before inference; oversize contexts fail instead of being silently truncated.

Generic instructions explain concrete unique IDs, prerequisite relationships, tool/analysis/artifact meanings, criteria against complete result JSON Pointers, typed references with one concrete type, and the difference between owner-requested source reads and managed report writes. Analysis instructions describe operation arity, verified prerequisite citations, optional parsed-JSON pointers, exact calculation semantics and source coverage. Composed arithmetic requires separate dependency analysis steps; report artifacts reference the verified analysis's deterministic `/data/text`. No goal template, expected fixture value, argument fallback or new authority is supplied.

Outline awareness is actual bounded original `host.route(goal)` plus original `discovery.search(goal, limit=8)` metadata, filtered by the original host eligibility policy and deduplicated to at most sixteen candidates. Descriptions are capped at 512 characters, argument/output names at 32 each. The already implemented own-artifact write boundary is separately described using the actual registered file.write definition. Awareness is labelled advisory and incomplete; every proposed tool step still receives its original independent binding menu. Prepared arguments, schema/hash binding, owner review, permissions, background admission, original registry dispatch and deterministic evidence verification are unchanged.

## Engineering evidence

| Artifact under `data/hanni-v3-review/` | Result |
| --- | --- |
| `m8-model-contract-affected-cycle-1.xml` | 183/183 PASS |
| `m8-model-contract-affected-cycle-2.xml` | 189/189 PASS, including new model-readable contract and complete operation semantics checks |

The overlapping cohort includes original planner/service/verification, registry guards, unchanged independent exposed planner/service/outcome/admission checks, generation-transport bounds and six new context checks. New checks establish exact full-schema visibility in both planning passes and the actual report call, combined context bounds before inference, genuine advisory discovery without handler execution, metadata confined to the untrusted data message, unchanged privacy refusal and a genuine isolated read/analysis/report artifact outcome through original handlers. Scripted responses and controlled resources are disclosed test seams.

Independent actual-runtime rerun of the unchanged public goals, original full regression and packaging validation remain required. Neither this patch nor the exposed public rerun restores unseen status to a previous once-only evaluation.

## Frozen hashes

| Path | SHA-256 |
| --- | --- |
| `src/hanni/workflows/transport_schema.py` | `3f622279727b2efef2c477a37281388842271c06971876f4d6fa9735f7f7083d` |
| `src/hanni/workflows/planner.py` | `93f6dba5617de377bbe6392c5ed480580aa2e730f466ab12d68dd0dfed1fd7a5` |
| `src/hanni/workflows/service.py` | `cc213f7a78d2e6f21351cfcf5df613453b465a82d90634dcfd1a90560084f629` |
| `tests/unit/test_workflow_model_context.py` | `439b48e11ce336ecf6dfa58f03916b64daf9e1ac445e469b7efd6b4199995796` |

Worker1 edits are limited to these three production paths, the new direct test file and this report. No configuration, public goal/oracle, model/runtime selection, local validation or execution permission was changed.

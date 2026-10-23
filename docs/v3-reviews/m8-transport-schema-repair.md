# Generic configured-runtime schema compatibility repair

Implementation candidate frozen after blocked-runtime checkpoint `3333a5f`. No sealed evaluator, input, oracle or raw model output was inspected; the original eighteen requests were not rerun. This repair does not establish model planning quality or real-runtime acceptance.

The configured llama.cpp build's schema converter turns bounded array/string lengths and patterns into grammar repetitions. The original outline nests steps and criteria with long strings, and the report nests observations and citations. The matching primary [C++ converter at commit 50f068fff](https://github.com/ggml-org/llama.cpp/blob/50f068fff/common/json-schema-to-grammar.cpp) also treats an empty schema as object-only; explicit type unions take a separate branch. The [Python companion](https://github.com/ggml-org/llama.cpp/blob/50f068fff/examples/json_schema_to_grammar.py) shows the corresponding behavior. These are converter observations, not an inference-quality diagnosis.

`workflows/transport_schema.py` supplies a detached response-format projection for all three workflow generation schemas: OUTLINE, BINDING and REPORT. It removes string-length, array-count and pattern constraints only at schema nodes, preserving types, required keys, enums and object-property restrictions. Unconstrained schema nodes explicitly admit object, array, string, number, boolean and null. Literal property names, enum/constant/default payloads are copied without interpretation. Explicit argument object schemas remain object-only.

The original schemas and configured local limits are unchanged. Original local JSON-schema validation, finite/depth/node/byte limits, token budgets, routing, prepared arguments, approvals, lease fencing, admission and deterministic report verification remain authoritative. There are no prompts, model/client replacements, automatic request retries, goal templates, or evaluation changes. The helper changes generation transport, never execution consent.

## Evidence

New direct tests use public synthetic values and scripted clients. They check schema immutability, structural/type/enum/key preservation, literal-key safety, transported-but-locally-rejected overlong strings/paths, oversized steps/criteria/dependencies, invalid step IDs, malformed JSON, nonfinite values and all JSON value types. An actual isolated original Service read-to-analysis-to-artifact workflow checks all three response formats and genuine local handlers; wrong calculations and oversized reports cannot produce the report artifact.

| Artifact under `data/hanni-v3-review/` | Result |
| --- | --- |
| `m8-transport-schema-development-cycle-1.xml` | 20/22 PASS; two own inspection-helper errors assumed enum-only schemas had a `type` key |
| `m8-transport-schema-affected-backend-cycle-2.xml` | 173/173 PASS after the test-helper correction |
| `m8-transport-schema-json-values-cycle-3.xml` | 183/183 PASS with unconstrained-value compatibility and finite-output tests |

These overlapping cohorts include original planner, service, verification, registry guards and unchanged independent exposed service/outcome/admission checks. They are not autonomous task-rate or configured-model evidence. Independent public actual-runtime grammar/Service smoke, full original regression and wheel verification remain required after this freeze. The once-only sealed evaluation remains blocked historical evidence, not a development input.

## Frozen source hashes

| Path | SHA-256 |
| --- | --- |
| `src/hanni/workflows/transport_schema.py` | `b96cb728c54b4e7b15302a60591a775db96b653c937fb67c2b6d9c7f5d318327` |
| `src/hanni/workflows/planner.py` | `f69db07a3e595e475c6806b42ef50d656cf406f2d9ed278d6a50492443ed11da` |
| `src/hanni/workflows/service.py` | `fb6dd28d083169a766150e4d9cf9bc0a67d421e8ebdbe43ca46fa7d5d7894363` |
| `src/hanni/workflows/verification.py` (unchanged) | `02baa196250b26619e22aeac0d30ec5221beeaaa09f3d773eb8b4230bbeaae5f` |
| `tests/unit/test_workflow_transport_schema.py` | `469c64f3f3d4b55da148466a4f23b9430c702efe73510eca0adaad83084a4bbe` |

Production edits are limited to the new helper and its two call sites. No configured model, native app, microphone, provider, node or production data was started or changed by Worker1.

# Generic reference, criterion and objective contract clarification

Candidate frozen after the failed public-cycle checkpoint `2ea8dff`. The unchanged public engineering smoke previously completed 0/2 objectives; this patch makes no claim that those outcomes have improved. Independent configured-runtime evaluation remains pending. Worker1 did not inspect sealed goals, evaluators or raw outputs, rerun the original eighteen requests, launch a model/native app, or alter public goals/oracles.

Only the planner's model-readable instructions changed in production. The binding message now supplies an exact reusable reference-object JSON Schema whose type enum is derived from the existing `references.KINDS`. It explains that an actual nested reference object can replace an argument before dependency resolution, and the original capability argument schema applies after resolution. A quoted pseudo-reference remains literal text and is never repaired or interpreted as a reference.

The outline message states the implemented criterion input types. `json_valid` selects JSON-encoded text, not a decoded object/array or an ordinary path. `expected` remains a literal JSON value. Other operators retain their existing non-null, collection/string, equality, finite numeric and verified evidence-report semantics. No criterion, argument, reference parser, full local schema or verification arithmetic was changed.

Generic decomposition instructions require retaining every requested operation and stopping condition, with each tool/artifact step representing one capability operation and dependencies preserving order. A step consuming an owner source retains that corresponding full source path; unrelated steps need not repeat it. Reads of generated artifacts use their verified predecessor path. No goal example, filename guessing, operation template, fallback argument, route substitution or automatic correction was added. Original routing, definition hashes, prepared arguments, consent, resource/lease/Stop guards and execution gates remain authoritative.

## Engineering checks

| Artifact under `data/hanni-v3-review` | Result |
| --- | --- |
| `m8-reference-criteria-contract-cycle-1.xml` | 192/192 PASS |
| `m8-reference-criteria-contract-cycle-2.xml` | 195/195 PASS |
| `m8-reference-criteria-contract-cycle-3.xml` | 195/195 PASS; final source |

Three added direct checks cover the exact displayed reference schema and existing type enum, post-resolution argument semantics and objective/path wording; genuine object-reference resolution versus unchanged quoted text and malformed-type rejection; and the actual existing verifier accepting encoded JSON text while rejecting decoded data and path text without rewriting criteria. The affected original planner, service, outcome, admission and registry-boundary cohorts also passed. These overlapping counts are not additive. Scripted planning clients and isolated resource probes are engineering seams, not measurements of configured-model intelligence.

Frozen SHA-256:

- `src/hanni/workflows/planner.py`: `dbbd91f33cf0d90a57faa4af77694eb1b4ab502a64ca0e8545f2d151fe2c52ac`
- `tests/unit/test_workflow_model_context.py`: `ca1556d7417d282870d694bb9b3065f501b80c69f3fc55bc13511197551678a1`

Worker1 changed those two files and this report only. The concurrent public-review harness diff belongs to the coordinator/verifier and was not edited by Worker1. Fresh full regression, packaging and unchanged public actual-runtime validation are required before acceptance. Residual omitted operations, invalid criteria, incorrect calculations or literal-reference choices remain observable model-quality failures; no unseen-quality or generalization claim follows from this repair.

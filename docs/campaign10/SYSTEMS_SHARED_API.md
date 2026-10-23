# Resumed Systems adapter contract

`scripts.campaign10_systems.shared.execute_input(case, case_root)` is an input-only adapter for **controlled original-service contracts**. It is suitable for the public verifier's `run_input` wrapper, which creates `case_root` before invoking the executor. The adapter uses a fresh `case_root/services` child and refuses existing state. It never receives an oracle file, dispatches by task ID, interprets a prompt into a plan, or creates a model client.

```python
from scripts.campaign10_systems.shared import execute_input
from scripts.campaign10_verification.adapter import run_input

receipt = run_input(public_input, fresh_case_root, execute_input)
```

The shared envelope must contain `version`, `id`, `family`, `difficulty`, `description`, `user_turns`, `fixtures` and `actions`. Actor profiles are exactly `owner` or `everyone_else`; `confirmed` must be an exact Boolean. The historical development label `default` is not promoted to owner. Explicit `fixtures.adapter` and supported actions are required. Sparse fixtures, missing required arguments, unsupported bindings and mixed actors return a measured limitation without inventing actions or seeding stores.

| Adapter | Supported operations | Important inputs and scope |
|---|---|---|
| memory / project | memory.retrieve, correct, delete, reopen, propose, review; project.resolve, package, alias, remove_alias, workspace | Explicit query/content/index/project/decision where required; original disposable stores. Direct persistence APIs are not registry actor-authorization proof. |
| workflow | workflow.run | One explicit goal/steps/mode fixture; goal must equal the supplied turn. Original controlled planner, service, registry, ledger and verification. |
| compute | compute.chat, withdraw, refresh | Explicit categories or observation field/value; original scheduler with mocked protected worker transport and synthetic context certification. |
| cluster | cluster.sample, snapshot | Explicit fixture mode; original monitor with mocked connectivity/telemetry. |
| voice_text | voice_text.classify | Explicit text; original relevance classifier. TEXT_ONLY is a scope field, not an evidence category. |
| voice_stop / voice_rate | voice_stop.run / voice_rate.run | Original pre-stop or format guard with controlled device/decoder leaves; no model or device acquisition. |
| screen | screen.awareness, project, invalid_image | Original unavailable awareness projection or image-format rejection; no capture or vision inference. |

Aliases are `memory.search`, `project.context`, `cluster.status`, `screen.status` and `screen.image_admission`, mapped to their corresponding operations above. Cross-action `bind` and action-level authority fields are unsupported. The bridge does not infer additional adapters from prose or unrelated operation names.

Owner workflow fixtures default missing `auto_approve` and `auto_start` to false. `confirmed:true` on an ordinary turn grants neither operation. Explicit fixture review/start controls remain controlled consent through the original revision, plan-hash and approval gates; they are not evidence that a model understood or obtained consent from the owner. A non-owner workflow submission reaches the original `WorkflowService.mutate` owner gate, with no attached planner or tool dispatch. Other non-owner direct-service interfaces and mixed actors are explicitly unsupported.

Literal workflow file paths must stay below the disposable root or managed artifact root. Typed file-path references must cite a declared predecessor's `/data/path` receipt from an owned `file.stat` or managed `file.write`. File contents cannot be reinterpreted as outside filenames. Artifact text may still use the original verified `/data/text` reference. Native dependency, type, approval and verification checks remain active.

The original workflow JSON Schema requires criterion dictionaries containing exactly `operator`, `path` and `expected`. The public input-only validator now admits only `expected:null` for `present`, `nonempty`, `json_valid` and `evidence_report`, at `fixtures.steps[i].criteria[j]` with `adapter='workflow'`. This permits native input syntax without exposing scored answers. Oracle fields and non-null expected values remain forbidden in the shared execution contract. The separately sealed historical development corpus and its schema correction are unchanged.

Every bridge receipt states `request_path_original:false`, `actual_generated:false`, zero genuine model/provider/remote/audio calls, and all ten model/task dimensions as `NOT_MEASURED` until independent prospective scoring. `original_adapter_invocations` counts adapter entries; internal native method calls remain unmeasured except the single witnessed non-owner mutation attempt. This bridge cannot replace the actual foreground controller executor for final natural-language tasks.

The genuine CLI path has separate prerequisites. `_workflow_command` recognizes `/goal` and `/workflows` and resolves an original dashboard-owned `WorkflowHub` for the exact data root. Text/MCP/memory wrappers alone do not create or attach that hub. Original workflow attachment requires the same registry, client and host, plus authentic telemetry/resource admission. `configured_retriever` selects enhanced `PersonalContextProvider` only with explicit configured context opt-in; otherwise it preserves legacy retrieval. Root owns actual controller attachment, model identity, resource budgets and live calls.

The resumed public smoke has nine prospectively sealed inputs: six reach controlled original adapters and three refuse unsupported/missing input. It records no adapter/harness exceptions and no real model calls. The final relevant test gate is **112/112**: 33 Systems checks and 79 public verifier-contract checks, 4.153 seconds. Its new tests include original actor denial, no automatic review, prerequisite failure, exact managed-artifact readback, source isolation and receipt scope. The earlier 101/102 run is retained: a new test assumed an undispatched native step contained `result:null`; the original receipt omits that field. The final test preserves the same assertion through an optional-field lookup.

Raw public receipts and the legacy seam reproductions are in `data/campaign10-systems/shared-smoke-resumed-cycle1`; read-only path-reference beforeproof is in `shared-path-reference-before`. The old smoke's `original_service_calls` meant adapter entries, and its summary field `actor_denied` accidentally held the original `accepted:false` value. Those bytes are preserved; current metadata uses explicit meanings. This worker changed no production source, old task input, old oracle or prior result. The manager's concurrent MCP source change is recorded separately in resumed source metadata.

The independent verifier confirmed five unchanged functional controls on the final bridge, plus two independently sealed path controls: outside filename reuse is refused before storage, while the managed artifact chain completes three verified invocations, one authorized write and exact original-source readback with zero duplicate effects. The seven controls are auxiliary public integration evidence. They did not invoke a real model, provider or private final task.

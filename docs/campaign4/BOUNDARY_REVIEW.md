# Campaign 4 workflow boundary review

The isolated original workflow service passed the final 66 focused checks and three fresh owned-process restart challenges. This is implementation evidence, using scripted structured planner output and controlled dependency data. It does not establish real-model goal understanding or physical cluster reliability. The independent final workflow set remains owned by the Manager and Verifier.

Baseline: `0aede831853b6876bc8904838a41f7b2ce8f3967`. Exact original bytes were archived before repairs in `data/campaign4-boundaries/original-source`. Public hashes, node-level receipts, transport counts and restart provenance are in [BOUNDARY_EVIDENCE.json](BOUNDARY_EVIDENCE.json). Original raw records remain under the ignored `data/campaign4-boundaries` directory.

## Independently reproduced defects and minimal repairs

| Boundary | Retained original evidence | Resulting behavior |
| --- | --- | --- |
| Pause/cancel between durable invocation admission and handler entry | `native-baseline-01`: 20 pass, 2 fail; independent `predispatch-before`: pause/cancel became BLOCKED, with zero handler entries | `service.py` reuses the original control-settlement path after a guard failure. Requested PAUSED/CANCELLED state is retained, parallel active calls remain visible until they return, and write uncertainty is preserved. |
| Continuation while an invocation remains uncertain or dispatched | `uncertain-scope-before-corrected`: 25 pass, 2 fail; independent `uncertain-control-before-corrected` proves both resume and an eligible original `file.stat` retry admitted a different managed write | `service.py` denies both resume and safe retry whenever any unresolved invocation exists. UI controls report the same reconciliation reason. Pause, cancel and revocation remain available. Finished eligible safe reads retain their original retry policy. |
| Generated static read source differs from the owner's explicit source | `source-controls-before-corrected`: 9 pass, 3 fail; independent `source-scope-before`: both outline substitution and binding-only substitution copied another file after reviewed approval | `planner.py` checks prepared literal local read resources against normalized original-goal paths. A mismatch blocks planning before dispatch. It preserves multiple sources, complete quoted/unquoted paths with spaces, normalized relative spellings, isolated UNC syntax and verified artifact references. |

The source-substitution defect is objective retention and argument consistency. The isolated owner had explicitly reviewed the wrong-source plan before execution, so the evidence does not establish a permission bypass. The source check rejects a mismatch; it does not silently replace a model argument or supply an expected answer.

The planner uses the existing metadata path pattern only to locate path starts. It extends unquoted spans to syntactic boundaries rather than trusting a truncated space-delimited token. Generic complete-filename boundaries preserve following prose and independently requested files without adding benchmark phrase exceptions. Typed declared prerequisite references retain the original resolution, verification, schema, scope and permission gates.

## Final focused evidence

`data/campaign4-boundaries/focused-final-01` records **66 pass, 0 fail, 0 skip in 22.093507 seconds**, with no source changes during execution. This comprises 54 new checks (27 service boundaries, 19 source contracts and 8 compute integrations) plus 12 existing model-context checks. The new source tests include positive controls for paths with spaces, multiple files, quoted UNC syntax without a network connection, unquoted component conjunctions, a shorter dotted-prefix rejection, unrelated preceding calculation and typed generated-report readback.

Native service probes traverse the original service, planner, MCP host and registry. They cover unavailable/busy planning, owner plan approval, sequential dependencies, safe local parallel reads, permission rejection, definition/scope invalidation, missing and partial evidence, optional-step failure, payload-bound request deduplication, pre-dispatch controls, active parallel withdrawal and uncertain-write continuation. Original file implementations run against disposable files. Selected barriers and errors are dependency seams; their scope is recorded instead of being counted as external provider or model quality evidence.

Post-repair denial assertions explicitly observe zero original read-leaf entries under `chat_only`, zero downstream report artifacts after missing/truncated evidence or uncertain-write continuation, and zero write-handler entries for rejected or withdrawn compute reports. The owned restart audit records one completed-source read each and write entries of one, zero and one respectively for safe recovery, before-write crash and after-write crash. Every recorded level-2 write is an owner request confirmed under the original reviewed scope. No other sensitive tool IDs occur. This is scoped evidence of no unauthorized dispatch or duplicate managed effects in these repaired controls, not a universal claim covering the deliberately failing baseline.

Fault seams are native service admission/definition/scope checks, the committed before-dispatch boundary, original file read/write/hash dependency leaves, post-result outcome persistence, missing/truncated result verification, parallel active-call guards, actual HTTP disconnection/timeout/late return and actual process lease-expiry recovery. The worker responsible for the store audits all direct transition/transaction edges separately. These service probes do not claim every store transition, disk/fsync crash, adaptive collaboration branch, physical SSH path or OS corruption was reached.

The Manager's broad regressions and local-analysis supplement are separate evidence. Their final source-frozen results must be taken from the Manager's campaign report, rather than inferred from these 66 checks.

## Actual controlled compute transport

Eight checks use original `ComputeRegistry`, `ComputeScheduler`, `InferenceTransport` and the native workflow analysis path against owned HTTP servers. **Ten actual POST requests** are recorded with request hashes and original job/invocation/checkpoint identities. Resource/context capacity fields are explicitly synthetic fixtures; no physical worker, GPU benchmark, SSH or owner model is contacted.

The cases prove that a socket disconnect blocks downstream writes when local fallback is disabled; an enabled fallback requires original authority rechecks and verifies its report; bounded reassignment preserves the failed first attempt in the same durable job; a complete HTTP response still requires independent cited-source verification; late pause/cancel responses cannot complete the analysis or write a report; and an actual HTTP timeout preserves the failed job while a new reviewed workflow succeeds after a genuine health refresh. Reservations are released at settlement. A filesystem leaf timeout is not used as evidence of remote inference disconnection.

## Owned-process restart challenge

`restart-final-01` passed in **2.907879 seconds**. The first real helper completes and durably verifies one original file read. A remaining native hash worker encounters a controlled `_sha256` leaf failure, and the engine persists its bounded retry checkpoint. The helper exits with code 83 during committed backoff. A distinct real helper waits for actual lease expiry, acquires a higher fence, observes PAUSED state without automatic execution, and explicitly resumes the remaining work.

The original scheduler then finishes the hash retry, remaining read, managed report write and report readback: **5 verified steps, 6 invocations**. The completed first step retains exactly one invocation and the same durable identity. Recovery makes zero planner calls. The report bytes match the actual source readback; SHA-256 is `519ba1c3965ab413b3fd141811f325a2d5051ea81602020c8b98fedfeb839317`. All five acceptance results are VERIFIED.

Two additional fresh process-crash boundaries passed without claiming workflow completion:

| Run | Crash boundary | Observed recovery |
| --- | --- | --- |
| `ambiguous-before-final-01`, 2.480968 seconds | Write invocation committed before handler entry | BLOCKED; completed source read remains verified; write remains uncertain; report does not exist; zero replay |
| `ambiguous-after-final-01`, 2.504781 seconds | Original write returned before its outcome was committed | BLOCKED; report exists but remains unverified; write remains uncertain; zero replay |

Both uncertain cases retain two invocation identities and refuse automatic or explicit continuation. Actual helper PID, parent PID, creation time, executable provenance, exit code, lease fence and receipt hashes are retained. Read-only cleanup checks confirm all six final helper identities have exited. Windows, HANNI and owner model processes were not restarted.

## Preserved failed attempts and fixture corrections

All failed runs remain available; later passing runs do not replace them. `restart-original-01` exposed a harness assumption that the Windows virtual-environment launcher PID equals its child Python PID; workflow restart/report outcomes had already succeeded. The corrected harness verifies the actual child-parent relationship and creation-time provenance. `uncertain-scope-before` included two premature samples of an intermediate state while another synchronous call remained active; corrected predicates preserve those calls until settlement. `source-before` incorrectly described ordinary `file.read` arguments as already router-pinned; the test was corrected to the independently authored source objective, allowing safe rejection or retaining the requested source. `source-controls-before` also used an invented calculator ID, corrected to original `calc.evaluate` before repair.

`source-repair-01` retains an implementation error referencing a nonexistent definition attribute; it was corrected to the registered argument schema. The first source-parser candidate introduced false rejections for following prose, plural-source adverbs and sentence punctuation. `source-continuation-before`, `source-plural-before` and `native-source-compute-current` preserve those failures, with prospective positive controls retained in the final suite. No development corpus objectives or private final oracles were changed to make these outcomes pass.

## Limits and source readiness

The source check handles bounded literal path syntax, not arbitrary natural-language objective entailment. Quoting disambiguates unusual filenames and extensionless paths followed by prose. Goals without explicit paths retain the original reviewed planning behavior. Typed dynamic references still rely on original predecessor verification and runtime authority; this static check does not prove that every requested operation was retained. `file.read` remains non-retry-safe, and interrupted analysis is not automatically replayed. Original native model admission and all permission gates remain intact.

Final production hashes:

- `src/hanni/workflows/planner.py`: `427faa317c795de6fd47abad7ffbf9fd71afc1666b69c64197607439d7c8e039`
- `src/hanni/workflows/service.py`: `ef0d76309eb314a8ab58a1b101b45918f36b04a4bc8ec4f83a44353753b7827c`

All owned Python source/helpers/tests use LF, and `git diff --check` is clean. No source changes are pending from this worker. Independent final results, live model outcomes and overall campaign acceptance are reported separately by the Manager.

The Manager froze the full implementation after source readiness: manifest SHA-256 `f7f3ef6ca9a9772223b0a3dd2a0947826e4f7b942f43a5bce53e2c36eda42e49`, archive SHA-256 `09de198ca6101c7cc1699464f1d1242d1fb0ed31ead88aa5c5524951cb17bf08`. This report may be updated with evidence while the source, harness, corpus, protocol and tests remain frozen.

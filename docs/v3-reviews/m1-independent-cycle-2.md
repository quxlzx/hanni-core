# M1 independent persistence cycle 2

**Original unchanged checks: PASS 10/10. Expanded robustness checks: FAIL 10/12.** All three cycle-1 defects are corrected. A separate root-requested deep-nesting review then found two uncaught recursion failures; these are retained before repair rather than replacing the prior ten-test result.

The independent rerun used the unchanged original test SHA `4252c9929b53e88f857caf570b4d986e9fd72334d58ae3ff25108353780f214d`. Evidence: `data/hanni-v3-review/m1-independent-cycle-2.xml`. Reviewed source hashes are `types.py` SHA `f776a78b10d848cf8659de09ee83e1f18872113f001a8146ccea2587b7dbe02b` and `store.py` SHA `8cabb5a30e8fe41206fa47a953a39ec0018e9cb60f2208e3750a3bb53cc7c8dd`.

Observed corrections preserve privacy and conservative recovery:

- Nested short generic token values are rejected before private encoding/persistence.
- Mixed abandoned write/read recovery aggregates state and remains blocked when any write is uncertain.
- Exact supported schema is checked before WAL/header changes, preserving unknown schema bytes.
- Existing actual owned-subprocess pre-dispatch/post-effect crash checks, live two-process owner arbitration and transactional approval/CAS rollback continue to pass.

The added exposed list/dictionary cases each construct finite JSON at depth 650. `json.dumps` succeeds, but recursive credential checking raises **RecursionError**, instead of the safe bounded **WorkflowError**. Exact tracebacks are retained in `data/hanni-v3-review/m1-independent-expanded-cycle-2.xml`; tests are appended in `tests/integration/test_workflow_store_verifier.py`. Root and Worker1 were notified. Severity is medium robustness: no credential is written and no authority gate is bypassed, but hostile bounded input can escape the expected failure contract. A bounded depth/node check before recursive redaction is appropriate; privacy validation must remain enforced.

The tests measure durable store boundaries and synthetic local side-effect ledgers, not an implemented WorkflowService or autonomous goal. Engine, actual model planning, background scope, original gated multi-step execution and native visual acceptance remain NOT TESTED. The eighteen sealed planning cases remain unchanged and unexecuted.

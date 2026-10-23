# M1 independent persistence cycle 1

**FAIL: 7 passed, 3 failed, 10 independent cases.** Root and Worker1 were notified to preserve this failed checkpoint before bounded repair and before M2 autonomy work. The source was Worker1's frozen M1 `types.py`/`store.py` after the first root review. The verifier edited only verification files.

Command: `.venv\Scripts\python.exe -m pytest -q tests/integration/test_workflow_store_verifier.py --junitxml=data/hanni-v3-review/m1-independent-cycle-1.xml`. Exact failure tracebacks are in that JUnit file; source/test hashes and additional actual SQLite credential proof are in `data/hanni-v3-review/m1-cycle-1-source.json`.

| Finding | Severity | Observed evidence | Required correction |
|---|---|---|---|
| Short generic credential key accepted | High | `canonical_json` accepts nested `token: "abcd"`; independent `WorkflowStore.create(...scope=...)` commits it and actual closed SQLite bytes contain the synthetic short token | Reject credential-bearing generic token keys before private persistence; preserve legitimate protocol identifiers without allowing credential values |
| Uncertain write hidden by later read recovery | High | Two independent steps have committed dispatched invocations, first a write and then a safe read. New owner recovery retains an `uncertain` write and blocked write step, but final workflow status is `paused` because the later read overwrites it | Aggregate recovery state across all affected steps; an uncertain write must keep the workflow blocked regardless of iteration order |
| Unknown version-1 schema changed before rejection | Medium | Existing version-1 tables include a renamed `payload` column. `list()` fails, but `_connect` has already changed journal mode: actual SQLite header byte 18 changes from 1 to 2 | Validate the complete supported schema before any write pragma/header modification; retain unknown schema bytes and fail closed |

The credential is synthetic fixture data, not a user's credential. The corruption fixture is an isolated SQLite file, not production history. No provider, SSH, power action, model, GUI, production assistant or user store was used.

Passing checks independently confirm:

- Three other nested short credential names are rejected.
- Stale approval/revision CAS failure rolls back approval consumption, step state and invocation creation together.
- Two real owned child processes cannot both claim the same live durable owner lease.
- A real child process killed by the committed pre-dispatch observer retains a blocked uncertain write after recovery; no replay occurs.
- A real child process terminated after an isolated fsynced side effect but before result commit retains exactly one effect and one uncertain invocation; no replay occurs.

These subprocess tests measure durable **store boundaries**. The effect is an isolated fsynced ledger under the test directory. They do not exercise a WorkflowService executor, original model planning, remote effects or a complete autonomous goal. M2–M8 engine/planning/background/native acceptance remains **NOT TESTED**. The eighteen sealed planning cases remain unchanged and unexecuted.

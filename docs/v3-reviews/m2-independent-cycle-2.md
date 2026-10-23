# M2 independent preparation cycle 2

**PASS: unchanged 36/36 independent exposed checks.** The 24 planner/policy/reference checks and 12 persistence checks passed against the coherent repair. Evidence: `data/hanni-v3-review/m2-independent-cycle-2.xml`. A separately executed implementation-owned protected-target preparation test also passed (1/1), retained in `m2-protected-target-preview.xml`; it does not increase the independent-case denominator. That preview checks the actual installed protected Notepad binary but stubs shortcut discovery to no match; it is not a live application launch or proof that a bare alias is unshadowed in the user's normal environment.

Both cycle-1 launch failures are repaired. Workflow preparation now resolves allowed application aliases to actual existing protected Windows system binaries using `GetSystemDirectoryW`, rejects working-directory shadows and uninspected shortcuts, and pins the exact target into fixed prepared arguments. The planner checks application selection against the original owner-goal router; model-supplied application arguments cannot replace that fixed target. Trusted workflow dispatch rechecks policy and hashes the prepared path. Default interactive dispatch retains its existing resolver. No Windows application is launched in these checks.

The passing original checks still reject model authority fields, invented or omitted required capabilities, unsupported prerequisites, malformed dependencies, analysis text offered as generic proof, Calendar scope widening and invalid/unverified typed references. All twelve persistence cases pass, including the prior depth-650 failures now rejected safely, exact schema preservation, crash uncertainty, lease contention and stale approval rollback. The two launch-failure oracles are unchanged. This closes the exposed M1 depth and M2 preparation defects; historical failure reports remain intact.

| Reviewed file | SHA-256 |
| --- | --- |
| workflows/types.py | `5a1a42030f2a92a976b10563d07bf1a0bbfa84492bc92150f3a63685108e389c` |
| workflows/store.py | `d2e1730c93c8962f3cfcd72878df615a859aac2868e429c49ea914968aec3f7d` |
| workflows/planner.py | `3ebef418fee2c1b022e21007afbe121c38e63671cb101b42e86167a0159932df` |
| workflows/policy.py | `2877ac6d195e1aeb624ad8879bf5a1127425fc54cf168341210c6c763eed2c1f` |
| workflows/references.py | `f1da6727d0c5b3e54d6ac76aa8854a8731b915053dfcac794e7cf66ca2faab3a` |
| mcp/host.py | `e8abe15fe5e4d669a6b3acbaba854d8682e4d3d360faa60e92126737ecb2e87b` |
| tools/base.py | `18fcbc3da3804d366fbc3c0f7399465c4395dfd3c11e5e618a3d3b44d770d4c2` |
| unchanged independent planner tests | `25b0d09502e4a47e68206c90eeb08c9dbb7be5582bd0475d06cf04821fe755ff` |
| unchanged independent store tests | `fea99f9eaadf9209bd41befe1292c66370d785540c3528c3c326a4f21fca7aa0` |

Scope remains preparation and persistence with scripted model replies, actual original metadata/router/gates and isolated filesystem fixtures. No real model, workflow engine, provider, shell, SSH, node power or voice session is started. Engine dispatch, semantic goal coverage, analysis truth, cancellation, timeout behavior, global budget, multi-step completion and native UI acceptance remain pending. The eighteen sealed planning cases remain unchanged and unexecuted.

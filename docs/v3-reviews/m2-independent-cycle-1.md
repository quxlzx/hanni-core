# M2 independent planner and preparation cycle 1

**FAIL: 34 passed / 36 exposed checks.** The initially frozen 22 planner checks plus all 12 persistence checks passed. Two additional root-requested application-resolution boundaries fail. M1's deep-nesting correction is independently accepted; M2 launch policy is not accepted yet.

Evidence is retained in `data/hanni-v3-review/m2-independent-cycle-1.xml` (34/34) and `m2-independent-expanded-cycle-1.xml` (34/36). The tests use two scripted model replies, real original registry metadata/router/host preparation, and isolated temporary files. They start no model, workflow runner, Windows application, provider, SSH session or remote action. The eighteen sealed planning cases remain unchanged and unexecuted.

The passing checks reject model-supplied authority, unknown capabilities, omitted required steps, invalid dependencies, unsupported requirements and generic analysis text presented as proof. Original Calendar fixed scope wins over model arguments, and unfixed temporal widening is rejected. Typed references require verified declared predecessors and exact types. Compilation executes no original tool handler. The twelve persistence checks retain genuine owned-subprocess crash boundaries and process lease contention, preserve unsupported schema bytes and reject depth-650 list/dictionary input with bounded WorkflowError instead of recursion failure.

The failed checks concern `app.open`:

- **High, launch target not pinned:** workflow policy accepts `notepad` when an isolated file named `notepad` exists in the working directory. The original Windows handler checks `Path(app).exists()` before any safe alias lookup and sends that file to shell-open. An approved alias therefore does not establish which target will be opened.
- **High, shortcut identity not established:** workflow policy accepts the same alias when original shortcut discovery selects an uninspected `.lnk`. The handler uses this shortcut before direct alias resolution. A display name does not establish a safe target or prove that shell/script execution is excluded.

These tests exercise policy with isolated shadow files or a stubbed shortcut lookup; no launch method runs. Source review establishes the subsequent original handler resolution order. Original read-only host restrictions can independently deny application calls; these findings are defects in the proposed workflow policy whenever the original session permits this action, not proof of an executed unauthorized application. A conservative workflow-only refusal is acceptable until an original-handler-compatible preparation path pins and verifies the executable target without arbitrary shortcuts, CWD/PATH shadowing or shell fallback. Interactive behavior should remain intact.

Root's captured-definition registry guard is present in the reviewed source: trusted workflow requests carry `expected_definition_hash`, while default session requests remain unchanged. Its dedicated race test is root-owned; this report does not count that test as an independently executed case.

Reviewed SHA-256:

| File | SHA-256 |
| --- | --- |
| workflows/types.py | `5a1a42030f2a92a976b10563d07bf1a0bbfa84492bc92150f3a63685108e389c` |
| workflows/store.py | `d2e1730c93c8962f3cfcd72878df615a859aac2868e429c49ea914968aec3f7d` |
| workflows/planner.py | `cdbd4d98e53dc637ed7481542b7386bfb6bfa14d83b511c580fdfe75723f3733` |
| workflows/policy.py | `5011084ba7dd71c2a49ce30723145d8a75528df94b4286c3827904f510861d98` |
| workflows/references.py | `f1da6727d0c5b3e54d6ac76aa8854a8731b915053dfcac794e7cf66ca2faab3a` |
| mcp/host.py | `81cec2718f89a2cf01aa3f59d8a59ab9e18a8455512f217215c8d4cbeae3c843` |
| tools/base.py | `18fcbc3da3804d366fbc3c0f7399465c4395dfd3c11e5e618a3d3b44d770d4c2` |
| tools/registry.py | `f7e82c0a1515e7cd82a7fa368a581cec249dbd3fd9a86911b38b928867f5787e` |
| independent planner tests | `25b0d09502e4a47e68206c90eeb08c9dbb7be5582bd0475d06cf04821fe755ff` |
| independent store tests | `fea99f9eaadf9209bd41befe1292c66370d785540c3528c3c326a4f21fca7aa0` |

An executable WorkflowService, actual model planning, original gated multi-step execution, final holdout quality, retention/maintenance and native visual acceptance are not evaluated by this stage.

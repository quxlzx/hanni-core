# Reliability V2 Activity: independent native cycle 1

**FAIL: first-fetch failure asserts an empty history.** This is a functional accuracy failure despite a usable visual layout. The source-frozen candidate produced 34 actual Win32 framed PNGs and 73/74 passing checks. Every PNG was independently opened and inspected. The executable and isolated server are closed.

Run: `.venv\Scripts\python.exe scripts/reliability_review/check_native.py --output data/hanni-reliability-v2-review/native-cycle-1`. The machine's observed DPI is 120 (125%). Actual framed sizes are 1920×1080, 1440×900, 1366×768 and 900×650; all matched their requested physical dimensions. No document horizontal overflow or JavaScript errors were observed. Other DPI values are untested.

The real portable executable attached to an original DashboardServer, original authenticated execution endpoint, original registry and real isolated trace store. Fourteen original `time.now`/`system.stats` executions, an original denied `file.write`, an original confirmed write into a temporary directory and its original `file.stat` verification, a cancelled service task, and two registered controlled fixture handlers produced 19 actual task records. File contents were independently checked outside the returned receipt; the trace reports `VERIFIED/read_after_write/requested_filesystem_state`, with both existence and content checks true. These observations establish that filesystem scope, not general user-task correctness.

Controlled seams: synthetic inactive telemetry; a registered read-only receipt handler and timeout handler; GeneratorExit inside the real observer's task context; and HTTP503 after the original token gate to exercise endpoint loss. Trace-storage unavailability was induced through the service's error state, not corruption of a user file. No frontend response/progress was fabricated. No model, microphone, provider, SSH or remote power action ran. Missing and incorrect private tokens were both rejected with403. The read-only receipt legitimately received returned-data evidence; this fixture is not evidence of unknown-mutation verification. A future run will separately include an actual controlled reversible-write receipt.

## Required correction

Owner: Worker2, `ExecutionTracePanel`. Severity: medium, acceptance blocking because this interface communicates reliability evidence. At initial endpoint503, the panel shows an unavailable error and also says “No task traces recorded yet.” No successful history read occurred. Render a distinct unavailable/no-data state; use the empty-history claim only after an available successful response. Preserve previously loaded records with the stale warning after a later failed refresh.

Evidence: [compact first-fetch failure](../../data/hanni-reliability-v2-review/native-cycle-1/initial-fetch-error-900x650-native.png); the same contradiction appears in all four first-fetch frames. The test “First-fetch error does not assert empty trace history” is the sole failure in [results.json](../../data/hanni-reliability-v2-review/native-cycle-1/results.json).

## Independent visual assessment

This task does not specify a new numerical visual rubric. The following review uses five explicitly equal two-point dimensions, rather than presenting the score as a newly mandated user rubric. Functional acceptance remains FAIL regardless of the numerical score.

| Dimension | /2 | Evidence and limits |
|---|---:|---|
| Typography and hierarchy | 1.76 | Clear Activity/task/history levels and readable monospace identities; secondary lifecycle times are small. |
| Layout and information density | 1.72 | Compact rows expose execution and verification separately; 900px expanded facts stack and push evidence below the fold. Normal vertical scrolling reaches the evidence. |
| Spacing and consistency | 1.76 | Matches the existing desktop rows, borders and input spacing; no nested card clutter or sideways overflow. |
| Professional appearance | 1.78 | Restrained graphite workspace, real evidence labels and native frame; no marketing template ornaments. |
| Interaction polish | 1.55 | Expansion, filtering, search-empty, stale refresh and token gates work; initial unavailable falsely asserts empty history. |
| **Total** | **8.57/10** | Actual pixels and observed controls only; not a functional pass. |

AI-template score: **1.0/10** (lower is better). There are no gradient headlines, placeholder testimonials, glass cards or fabricated popularity signals.

Useful frames: [recorded at1920](../../data/hanni-reliability-v2-review/native-cycle-1/recorded-1920x1080-native.png), [recorded at900](../../data/hanni-reliability-v2-review/native-cycle-1/recorded-900x650-native.png), [expanded filesystem evidence](../../data/hanni-reliability-v2-review/native-cycle-1/expanded-file-evidence-1366x768-native.png), [compact evidence after scroll](../../data/hanni-reliability-v2-review/native-cycle-1/expanded-evidence-bottom-900x650-native.png), [stale refresh](../../data/hanni-reliability-v2-review/native-cycle-1/stale-refresh-900x650-native.png), [storage unavailable](../../data/hanni-reliability-v2-review/native-cycle-1/unavailable-storage-900x650-native.png). All34 frames, DOM diagnostics, original task records and check outcomes remain in the ignored artifact directory.

## Artifact identity

No recorded source/artifact hash changed during capture. Full start/end hashes are in results.json.

| Artifact | SHA256 |
|---|---|
| Portable executable | `9bf90dc1438e1776369f668117d88c2a5f76a33fc6f796c4d9f41a8a7e586263` |
| app.js | `daed0cbfaa71ac6f13be4ed5bf73db11038f3b60801c3b12bfa3a9f3de654f51` |
| style.css | `92aa1f143f097054a3c10c634f9ac75aff9f4758aeb0b005f21b39c50528c01d` |
| execution.py | `597c115aa30c541b64e8a3c55c63cc65b6d79428f46798cd2cd188537b2ecdf2` |

The restart/persisted waiting-approval issue reported by the coordinator is not exercised by this capture cycle and remains a separate required backend check. Sealed final holdout cases were not read or run against this candidate.

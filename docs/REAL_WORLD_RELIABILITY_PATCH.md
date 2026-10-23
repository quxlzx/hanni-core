# Real-world reliability patch

## Behavior changed

- Calendar reads resolve owner dates before model tool selection, including casual weekday and daypart language. Google reads return the exact local query window, source calendar IDs, event count, and fetched timestamp. Point and interval availability use event overlap with exclusive ends; all-day event dates are handled as local midnight boundaries.
- Calendar creation requires an exact clock time when the owner provides only a daypart. A Google response must include an event ID before HANNI reports creation, and successful writes state that they were not read back.
- Disk inventory answers use measured mounted partitions. A requested absent drive is reported as absent, without invented capacity. Current Calendar, disk, and model-status answers use their tool messages instead of ungrounded model wording for a single request.
- Direct app launches report `process_started` with a PID. Shell and shortcut handoffs remain `accepted` until a window is observed. The completion ledger accepts the former as a completed process start without claiming a window was verified.
- Media follow-ups carry the last explicit player through short controls, then reset on a topic change. File search defaults to Downloads, Documents, and Desktop, ranks filename matches, and skips dependency directories and sensitive paths. A location follow-up retains the earlier search request.
- A diagnostic answer that promises another check gets one bounded continuation when an unused read-only tool is available. Debug mode logs redacted routing decisions, tool arguments, Calendar query metadata, evidence IDs, and final responses.

## Root causes found

| Failure class | Cause |
| --- | --- |
| Calendar day returns empty or wrong date | Casual `what's on` phrasing and dayparts missed the deterministic Calendar read path; the result lacked resolved-window metadata. |
| Availability contradicts an event | The model was left to infer availability from event lists. |
| Evening write becomes an all-day event | The date parser treated a daypart without a clock time as an all-day date. |
| App visibly opens but HANNI reports failure | A successful direct `Popen` was labeled only as an unverified shell request. |
| Generic media follow-up loses Spotify | Context checked only the last user turn, including bare `pause it`. |
| Personal file search returns project internals | Unqualified search began at the working directory and returned traversal order. |
| Diagnostic says it will check and stops | The continuation loop considered only outstanding requested subtasks, not a promised next read. |

## Verification

From the repository root:

```powershell
py -3 -m pytest -q
$env:PYTHONPATH='src'; py -3 -m hanni.evals.real_world_reliability
```

The development evaluation has 100 independent route probes in ten families and does not access the sealed live-session artifact or execute actions. It checks candidate-tool coverage, not end-to-end model responses. The complete test suite passes with three skips; one skip is the historical `language_v2_qwen_dev150_final.json` report absent from this checkout.

Files changed for this patch: `src/hanni/tools/{calendar_routing,google_access,whenparse,storage,windows,files,language_concepts,routing_intents}.py`, `src/hanni/mcp/{host,session,completion}.py`, `src/hanni/evals/{llm_tools,real_world_reliability,live_holdout}.py`, `evals/llm_tools/capability_coverage_v1.jsonl`, `tests/unit/test_real_world_reliability.py`, `tests/evals/test_real_world_reliability.py`, `tests/evals/{test_llm_tools,test_failure_ledger}.py`, and this report. Earlier uncommitted dashboard stop-button and Spotify changes were preserved.

No migration or production model/configuration change is required. Google Calendar reads and writes still require the existing owner-authorized Google connection. The three bake-off model files were downloaded into the user's Hugging Face cache, outside the repository.

## Limitations

- A shell or shortcut launch may still be accepted without a detected window. HANNI reports that level honestly.
- Calendar writes are confirmed by the returned Google event ID; this patch does not perform a separate read-back request.
- `model.status` verifies GPU placement only for a live HANNI-owned llama.cpp process with a matching offload log. An external server remains unverified.
- Daypart availability returns events for the resolved day; it does not assert that the entire morning or evening is free without an explicit clock interval.
- File search is bounded by time and entry count and reports truncation. It cannot guarantee that every file in a large tree was scanned.

## Holdout handling

The supplied final holdout has SHA-256 `4d4aa9e7a65f3122c0aba78657ff7f0b50a6956628fbccb07fe458f6ac7ba0e6`.
The first read of the attached files accidentally printed part of the JSON before its sealed-use rule was read. Therefore `HOLDOUT_INTEGRITY = COMPROMISED`. No holdout cases were used to make this patch or the development evaluation.

The final model comparison is in `MODEL_BAKEOFF_FINAL.md`. It shows low mechanically scored results and unassessed semantic turns. This patch passes ordinary tests, but should **not** be called reliability-complete or safe to merge on the supplied acceptance criteria without a new independent holdout and owner review. No results were used to tune HANNI after the final run.

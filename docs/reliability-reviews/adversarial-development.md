# Independent reliability adversarial development cycles

These are independent verification-only tests in `tests/integration/test_reliability_verifier.py`. Production source was under active development; none of these runs is described as acceptance of a frozen milestone.

- Cycle 1: 15 cases, 11 passed and four failed. Evidence `data/hanni-reliability-v2-review/adversarial-cycle-1.xml`.
- Expanded cycle 1: 18 cases, 14 passed and the same four failed. Evidence `adversarial-cycle-1-expanded.xml`.
- Cycle 2 after implementation-owner bounded corrections: 18/18 passed. Evidence `adversarial-cycle-2.xml`.
- Expanded cycle 3: 21 cases, 20 passed and one newly discovered failed. Evidence `adversarial-cycle-3-expanded.xml`.

## Concrete failures preserved

The first four failures were malformed process metrics falsely classified VERIFIED, empty Spotify data falsely providing partial playback evidence, a follow-up verifier executing a capability marked reversible_write despite zero permission/risk metadata, and a denied non-owner action reported failed rather than rejected. Worker 2 corrected production source without weakening the verifier's assertions. The independent cycle-2 rerun passed all eighteen cases.

The remaining cycle-3 failure concerns the bounded trace limit: sixty-four successful controlled registry reads followed by an actual failing sixty-fifth handler response cause `trace.begin` to return None; the later failure is dropped and the final task falsely reports succeeded/VERIFIED. The record must retain bounded overflow failure/uncertainty metadata rather than silently presenting complete success. Worker 2 and root received this finding before repairs.

## Passing security and lifecycle evidence

Actual original registry gates remain active in every controlled handler test. Passing cases show non-owner handlers never execute; follow-up reads require the same actor's approval and stop gates; stopping after a write prevents the verification read and never repeats the action; a content-hash mismatch remains unverified; unknown mutation receipts and external MCP self-assertions cannot establish independent verification; failed non-idempotent replay is suppressed; explicitly safe built-in read retry is bounded to one retry; external MCP timeout does not assume replay safety.

Payload/message/source-suffix privacy was checked in actual trace snapshots and SQLite bytes. Corrupt and future-version SQLite bytes were preserved while an action still executed exactly once. Model protocol failure status, mixed-success partial tasks and GeneratorExit cancellation have explicit observed outcomes. These tests use controlled handlers/deterministic probes and are not presented as actual configured-model inference.

Next independent rerun follows the implementation owner's overflow correction. Final milestone acceptance also requires coherent full regressions, forty controlled workflows with original/final replay, actual configured-model comparison and native observability inspection.

# Independent cycle 4: bounded corrections rechecked

All **22 independent cases pass** in `data/hanni-reliability-v2-review/adversarial-cycle-4.xml`. The previous overflow defect is retained above as failed-cycle evidence: a 65th failing handler after 64 recorded successful steps now prevents a fully verified success projection.

An added restart test uses the original ToolAwareSession and original temporary-file delete capability to enter the real confirmation boundary. The file remains present. After closing the original service and loading the same real store into a new service, that record is `approval_unavailable`, `approval_active=false`; its original events and steps remain unchanged. A new ToolAwareSession receiving “yes” cannot replay the historical request, and the file contents remain intact. This is a restart/session-availability assertion, not stored-request replay support. No production implementation was edited by the verifier.

## Independent cycle 5: unknown partial mutation receipt

The expanded suite runs26 cases:22 pass and4 new cases fail. Evidence: `data/hanni-reliability-v2-review/adversarial-cycle-5.xml`. `inspect_result` elevates an unknown reversible-write receipt to PARTIALLY_VERIFIED when its data contains any of `partial=true`, `truncated=true`, a nonempty `errors` array, or `state=partial`. The fixture supplies only a received acknowledgement; it performs no state check and exposes no recognized outcome evidence. Partial metadata alone cannot establish that any requested mutation scope happened. The early generic partial branch must retain conservative mutation evidence rather than transferring read-excerpt semantics to unknown writes. Root and Worker2 received the concrete failing assertions before final freeze. Previous22 passing cases remain unchanged, and no production implementation was edited by the verifier.

## Independent cycle 6: conservative partial receipts rechecked

After the implementation owner's bounded correction, all **26 cases pass** in `data/hanni-reliability-v2-review/adversarial-cycle-6.xml`. The four receipt flags no longer elevate an unknown mutation outcome; unchanged previous assertions cover original authority gates, read-only followups, non-replay/retry bounds, privacy, corrupt-store retention, trace overflow, cancellation and historical approval inactivity. This targeted PASS does not replace the still-required coherent final broad regression or unseen/configured-model comparison.

## Independent calendar requested-title failure

The additional `test_calendar_readback_wrong_requested_title_is_not_verified` fails in `data/hanni-reliability-v2-review/adversarial-calendar-title.xml`. A controlled provider read through the original registry returns a matching identifier and schedule but a different appointment title from the explicitly requested summary. `verify_action` projects `VERIFIED/created_calendar_resource` because its checks only compare identity and time. This is an observed gap in requested-state claim support, distinct from the workflow oracle's disclosed lack of independent language-to-clock validation. The verifier sent the concrete failure to root and Worker2 before final freeze; no production feature or final holdout was changed.

## Frozen broad regression and calendar-title correction

The verifier parsed `data/hanni-reliability-v2-review/m3-full-corrected.xml`: all **27 independent adversarial cases pass**, including the unchanged wrong-requested-title assertion. No duplicate targeted execution was performed while the coordinator ran this coherent broad suite. The complete suite records1057 passed,2 existing skips and17 passed subtests; its1076 JUnit testcase entries have zero failures/errors. Runtime141.481s in JUnit, coordinator wall time141.57s. The historical failing calendar-title artifact is retained. This establishes bounded corrected-source regression/gate evidence; live-model intelligence, provider outcomes and native frozen-byte acceptance require their own observations.


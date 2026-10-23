# Phase 1 and Phase 2 independent verification audit

Reviewed 2026-10-09 by the independent verifier. Application code is outside this
agent's ownership. New feature acceptance is pending actual implementation and
native verification; earlier screenshot scores do not grade new features.

## Verified starting point

Starting checkpoint: `3b83267`. Main reran the baseline: 788 tests passed,
2 skipped and 17 subtests passed. The previously inspected executable scored
8.78 overall (Home 8.7, Conversation 8.8, Mission 8.7, Cluster 9.0, Settings 8.7),
with AI-template score 1.14. Details and limitations remain in `iteration-2.md`.

The new request brief at attachment `0ad0c11a-8ecc-4102-ad2a-be4ffedc2dac`
was read in full before this audit. Exactly three existing actual agents are
reused. No GUI, microphone stream, model, screen capture, node power operation,
or terminal launch was started during this audit.

## Capability evidence and truthful limits

| Area | Audited baseline | Verification consequence |
| --- | --- | --- |
| Desktop and Cluster | Previous actual native captures, lifecycle/security checks, real local and eight-node telemetry | Recheck changed artifact and interactions; retain prior evidence only for unchanged behavior. |
| Mini | No existing secondary native Mini or global hotkey | Must test real hotkey from another foreground application, focus, dismissal, pinning, expansion, shared chat, conflict and shutdown behavior. |
| Agent activity | Tool audit and ChatHub queue exist; jobs control definitions alone do not establish a wired live manager | Show observed states, not fictional agents or unsupported cancellation. Full requested agent lifecycle remains unverified. |
| Tasks and calendar | Existing TodoStore and authorization-protected Google capabilities | Exercise additive persistence, restart, errors and existing permission path; never substitute a bypass executor. |
| Memory | MemoryStore has get/list/search/delete/forget and source/confidence/timestamps | Test real supported store through isolated data, sensitive-read protection, confirmed deletion, validation and stale-data handling. |
| Screen awareness | Privacy schema has exclusion patterns and retention capped at 120 seconds; no screen capture or configured vision pipeline found | A truthful unavailable interface is useful but does not complete screen analysis. Actual analysis remains blocked without a supported pipeline. |
| Voice | Existing microphone/VAD/STT/relevance/TTS/barge-in stack and measured input observer | UI status must reflect runtime truth. Device presence is not proof of capture, wake, audible playback or latency. |
| Notifications | Existing bounded deduplicated transient job notifier | Verify new persistent history, actual event provenance, redaction, deduplication, preference changes and original approval gates. |

The baseline workspace contract explicitly reports agents, planner, memory
browser, screen awareness and output audio levels unavailable. New UI labels
cannot make those capabilities available by themselves. Registered tools and
privacy configuration are evidence of integration points, not completed screens
or live feature operation.

Read-only audio enumeration succeeded through existing audio-device code:
Realtek microphone inputs include WASAPI, and Windows speech exposes a Realtek
speaker output. No stream opened and no audio was played. This confirms detected
hardware only. Genuine wake-to-listen, end-of-speech-to-response, first-audible
and interruption latencies remain **unmeasured** until a coordinated real test;
synthetic PCM or mocked timing must be labeled separately.

## Milestone acceptance procedure

Every milestone freezes source, bundle and executable before independent review,
then receives a checkpoint from the main coordinator. Native packaging and GUI
tests run sequentially to avoid locked DLLs and obscured screenshots.

Capture actual foreground framed executable windows at physical 1920 x 1080,
1440 x 900, 1366 x 768 and a small resized window, at the observed Windows 125%
(120 DPI) scaling. Use DPI-aware Win32 coordinates. Open and inspect each primary
screen, including new screens, plus applicable idle/disconnected/loading/error,
dialogs and native Mini states. Record artifact hashes and disclose fixtures.

Score legibility, hierarchy, spacing, information density, consistency and
interaction clarity from actual pixels. Every primary screen must score at
least 8.6, overall above 8.5 and AI-template at most 2. Functional failure cannot
be offset by a visual score. Repeat independent review after material fixes.

Mini checks will include a genuine native global shortcut, keyboard flow,
Escape hide, actual always-on-top style, expand into shared conversation,
single submission/no duplicate tool execution, user-configurable conflict
behavior, backend unavailable behavior, both windows' navigation/request guards,
and cleanup without stopping unrelated backend/voice sessions.

Phase 2 checks will separate isolated store/controller integration, synthetic
edge-state rendering, and genuinely live device/model/provider operation.
Missing configured services or hardware evidence receive explicit PARTIAL or
BLOCKED statuses. User data, credentials and private audio/screens must not be
copied into shared reports. Remote power and terminal handlers remain inert in
visual fixtures.

## Pending

Await the main coordinator's build freeze and GUI GO. New Mini and Phase 2 native
captures, feature tests, real voice timing and per-milestone scores have not yet
run. This audit does not grant final acceptance to the new request.

# HANNI desktop workspace integration

The desktop and Mini use the existing loopback dashboard, ChatHub and controller.
Mini submits the same UUID-bound `/api/chat` request as Conversation; its native
bridge exposes window controls only. Model loading, routing, MCP tool selection,
wake classification and existing CLI entry points retain their original owners.

Native readiness, shutdown identity and optional notification delivery request
`/api/chat?before=1` through the existing history cursor. They need only the token
and session identity, so this avoids loading a large conversation unnecessarily.
Full Conversation and Mini still load their normal shared history. Mini waits for
all five injected window methods to be callable before requesting native state.

## Personal data and actions

All seven new GET projections require the current launch's `X-Hanni-Token`.
The token stays in memory; it is not saved to workspace or desktop preferences.
Existing Host, Origin and cross-site checks apply to both old and new routes.

| Route | Source and behavior |
| --- | --- |
| `/api/productivity` | Existing task database with additive project, note, link and priority metadata |
| `/api/memory?q=...` | Existing configured MemoryStore, bounded search with provenance |
| `/api/calendar?start_date=YYYY-MM-DD&days=1\|7` | Local cache and existing account connection metadata; remote read only with explicit `refresh=1` |
| `/api/agents` | Current controller/ChatHub state, existing registered capabilities and redacted tool audit |
| `/api/awareness` | Actual unsupported capture/vision status and configured retention policy |
| `/api/voice` | Bound attentive session's capture, interaction, input amplitude and observed timing scalars |
| `/api/notifications` | Persistent history projected from actual audit, model/cluster transitions and local due tasks |

Productivity, memory deletion and notification POST requests accept exactly
`{id, operation, data, confirmed:true}`. Operations are fixed allowlists, not a
generic tool runner. Every record write passes through the existing ToolRegistry,
profile authorization, confirmation requirements, emergency stop, mutation lock
and audit. Private workspace arguments/results are redacted from the shared audit.
UUID retries bind to the exact payload; a reused ID with different data is rejected.
Persistent task/notification ledgers also prevent duplicate writes across restart.
Updates and deletes compare record fingerprints; memory deletion atomically checks
the timestamp in its SQLite transaction. Stale edits fail instead of overwriting.

Task completion remains visible to existing TodoStore tools. Undated UI tasks use
the original non-null `due` column with an empty value; the existing overdue query
excludes those rows. Projects, notes and links use additive tables in `todos.sqlite3`.
Project deletion confirms the selected project and removes its notes/links, while
retaining associated tasks without their project association. File links prepare
an existing-controller conversation request; they do not execute shell commands.
Conversation links open the exact saved message when it is in accessible history.
Calendar event creation and memory corrections prepare supported conversation
requests for the same controller and its existing permission flow.

## Persistence, backup and recovery

Workspace schema version 2 is recorded in its own metadata table. Migrations leave
the original task schema intact, use transactions and create an integrity-checked
SQLite backup before an existing workspace schema upgrade. New databases do not
require a migration backup. There is no automatic reset on migration or read error.

The workspace Backup action uses SQLite's backup API and `PRAGMA quick_check`,
writing an original filename under the configured data directory's
`workspace-backups/`. The client cannot choose a destination. This backup includes
tasks, workspace metadata, cached calendar events, notification preferences/history
and request ledgers. It does not include the separate memory database, credential
vault, model weights or chat store.

Recovery is deliberately manual. Stop the controller and all clients, copy the
current data directory and chosen backup to a separate safe location, verify the
backup's `quick_check`, then explicitly restore the intended database while all
writers are stopped. Preserve the original database and any journal/WAL companions
in the safety copy. Never restore over a running service or treat an empty store as
proof that old data should be deleted. No destructive restore endpoint is exposed.
The request ledger has a 50,000-entry limit and fails closed at capacity rather
than silently removing deduplication history.

## Voice adapter and measurement limits

Only the existing attentive CLI loop binds VoiceControl. Opening the UI does not
start recording, STT, a model or speech playback. Mute stops the existing capture
pump; unmute requires the old worker to have exited and creates a fresh instance
of the original configured pipeline. Old in-flight transcripts are discarded.
Muted queue consumers keep their bounded wait so they do not busy-spin. Resume
checks the existing emergency-stop gate. Manual Listen calls the original wake
classifier to arm the session; it is not evidence of spoken wake recognition.
Interrupt stops the existing owned playback/completion handles.

Input animation uses the existing microphone amplitude observer. There is no
invented output waveform. Device selection uses the existing audio-routing API
and its restart notices. UI state distinguishes disabled, standby, listening,
processing, speaking, muting and muted.

Timing scalars use original audio/interaction timestamps. Wake timing currently
means **end of the wake utterance to classification**, not first wake phoneme to
listening. Response timing ends at the first streamed chunk. Interruption timing
measures the original stop call. First audible response remains null because no
audible-output onset sensor exists. Unit timings are not live hardware evidence.
Actual spoken wake, transcription, audible TTS and barge-in need a coordinated
microphone test and must be reported separately from automated regressions.

## Honest availability

No autonomous registered agent runtime, live approval queue or universal
cancellation API is wired in this checkout. Agents displays the real HANNI
controller and capabilities; Activity displays recorded tool lifecycle fields.
Missing durations, requests, approval details and results are labeled unavailable.
No hidden model reasoning is shown. Approval notification preferences do not
create an approval backend, and inspecting a notification cannot authorize a tool.

Screen capture/vision is **blocked**: the repo has retention/exclusion configuration
but no registered capture or vision pipeline. The screen reports capture inactive
and context unavailable. It captures, saves and uploads no frames. The status UI
does not satisfy the requested screen-analysis milestone.

Remote cluster data comes from the unchanged fixed-roster SSH/Tailscale collector.
Tailscale presence is distinguished from successful telemetry. GPU/storage fields
are unavailable where the collector does not support them. Yunjin remains in
repair with a jellyfish and no probe. Existing power confirmations and fixed-node
terminal actions remain authoritative.

Notification history deduplicates source keys, groups categories and persists
read/dismiss/preferences. Informational events are limited per category; repeated
model failures and node disconnects are cooled down for 60 seconds. Native
notifications are optional, ignore history on first attach and share a bounded
rate limit. Preferences and notification actions do not bypass tool policy.

## Validation and continuation

See [milestone checkpoints](HANNI_PHASE12_CHECKPOINTS.md),
[desktop startup](HANNI_DESKTOP.md) and the independent reports under
`desktop-reviews/`. Native review uses the packaged executable, four physical
window sizes and disclosed isolated fixtures. Persistence verification must
exercise original stores and reopen the service; synthetic health/provider data
cannot establish live inference, external calendar authorization or voice timing.

The remaining screen-analysis work requires an actual supported local vision
pipeline, permission-gated capture, expiration and explicit conversational context
handoff. Wire that capability before enabling its controls. Do not infer support
from privacy settings or install a second model router to fill the gap.

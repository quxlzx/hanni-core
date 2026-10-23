# Google capability layer: implementation report

## Summary

Implemented a shared Google access layer for Calendar, Gmail, Drive, native Docs text and Google Tasks. Added named accounts, service-specific grants/defaults, short-lived account-bound result references, safe API errors, bounded routing menus and write gates. Qwen3.5-4B, local inference and the production `America/New_York` timezone remain unchanged. No commit, push or publication was performed.

The existing Calendar and email routes remain compatible. Unqualified reads now use one default account; they no longer search every connected account. Google initialization remains lazy, so startup and local commands do not require Google connectivity.

## Files changed

| Area | Files |
| --- | --- |
| New shared identity/scopes | `src/hanni/tools/google_identity.py` |
| New Drive/Docs/Tasks and canonical capabilities | `src/hanni/tools/google_services.py` |
| New Google routing/reference state | `src/hanni/tools/google_routing.py` |
| Existing auth, API access and CLI | `src/hanni/tools/google_access.py`, `google_auth.py`, `src/hanni/cli.py` |
| Registry, account routing, audit | `src/hanni/tools/registry.py`, `calendar_routing.py`, `email_provider.py`, `audit.py` |
| Session integration and completion checks | `src/hanni/mcp/host.py`, `session.py`, `completion.py` |
| Offline evaluation isolation | `src/hanni/evals/isolation.py` |
| New integration regressions | `tests/unit/test_google_services.py` |
| Updated compatibility tests | `tests/unit/test_google_access.py`, `test_capability_metadata.py`, `tests/evals/test_llm_tools.py`, `test_routing_benchmark.py` |
| Added routing/schema fixtures | `evals/routing/cases.jsonl`, `evals/llm_tools/cases.jsonl`, `capability_coverage_v1.jsonl` |
| Setup/security/capability documentation | `README.md`, `docs/GOOGLE.md`, `docs/HANNI_CAPABILITY_MATRIX.md`, `.env.example`, `.gitignore`, this report |

The workspace also contains earlier audio/dashboard changes. Those remain separate from the Google implementation.

## Capabilities added

Twenty canonical capabilities bring the registry to 172:

- Calendar: `google.calendar.events`, `next`, `availability`, `create`, `update`, `delete`, `list_calendars`, `read`.
- Gmail: `google.gmail.recent`, `search`, `read`, `thread`.
- Drive: `google.drive.search`, `list`, `recent`, `metadata`.
- Docs: `google.docs.read`.
- Tasks: `google.tasks.list`, `create`, `complete`.

Each abbreviated name above uses the family prefix on the same line. Legacy capability IDs remain registered. Calendar creation requires explicit resolved intent, write scope and policy. Calendar update/delete and task completion verify an exact source ID and require confirmation through the manual CLI. Google task creation additionally needs an owner-configured session allowlist entry for natural-language execution.

## Scopes and security

Default login requests `userinfo.email`, `calendar.events.readonly` and `calendar.calendarlist.readonly`. Optional groups add `gmail.readonly`, `drive.metadata.readonly`, `drive.readonly` for Docs export, `tasks.readonly`, `tasks`, or `calendar.events`. Full URLs, group mappings and commands are in [Google setup](GOOGLE.md#oauth-scopes).

Tokens, account indexes and preferences use Windows Credential Manager. There is no plaintext refresh-token fallback. Client JSON and token filenames are ignored by Git. The filename check found no tracked OAuth/token JSON, and confirmed the local client path is ignored. Token values and raw API error bodies are not printed. Google audit content and queries are suppressed.

The model cannot change an unqualified request to a different account or all accounts. Fixed owner arguments override model arguments. Cloud data is treated as untrusted tool data. Google references retain only IDs/account/minimal metadata and expire after 15 minutes; document/mail bodies are not stored in reference state. The dashboard's existing policy for displayed chat history still applies.

## Verification

Tests used injected API fixtures; no live Google data was read or modified and no OAuth flow was started.

| Check | Result |
| --- | --- |
| Full suite: `.venv\Scripts\python.exe -m pytest -q --tb=short -o addopts=` | **679 passed, 1 skipped, 17 subtests passed** |
| New Google routing probes | **40/40 passed** |
| Full routing corpus | **1,129/1,131 passed (99.82%)** |
| LLM fixture menu/result audit | **194 scenarios, zero failures** |
| Registry coverage | **172 registered; 132 model-facing; each model-facing capability has two schema/menu probes** |
| Coverage errors / missing routing probes | **Zero** |
| `git diff --check` | **Passed** |
| CLI login help | **Validated** |

The two routing mismatches are `REGISTRY-folder.open-2` and `REGISTRY-spotify.play_pause-1`. Both were reproduced against the original `HEAD` host source with an execution-disabled registry. They are outside the Google changes. Existing frozen benchmark cases and test thresholds were preserved. The LLM corpus uses its declared Chicago fixture timezone; production still uses New York.

New regression coverage includes scope separation, custom labels, default/service account selection, no account fan-out, metadata-only Drive search, query escaping, partial/empty results, native Docs export, unique/ambiguous named documents, reference expiry, account switching, exact IDs, case-preserved IDs, write-scope enforcement, Calendar update/delete confirmation, task completion confirmation, revoked credentials, network/HTTP failures, secret redaction and API-failure grounding. Existing Calendar date/availability/create and email tests also pass.

Local evidence: `data/google-suite-final.txt` and `data/google-capabilities-verification.json` (ignored). These checks validate deterministic behavior and mocked contracts, not live Google permissions or live model selection quality.

## Setup and examples

Follow [Google setup](GOOGLE.md) to enable the desired service APIs and create a Desktop OAuth client. Then:

```powershell
.\.venv\Scripts\hanni.exe google login
.\.venv\Scripts\hanni.exe google login --replace --scopes calendar.read gmail.read drive.read docs.read tasks.read
.\.venv\Scripts\hanni.exe google login --account school --scopes calendar.read gmail.read drive.read
.\.venv\Scripts\hanni.exe google use school --service calendar
.\.venv\Scripts\hanni.exe google status --verify
```

Optional Calendar writes: `google login --replace --scopes calendar.write`. Task writes use `tasks.write`; see the guide for session policy and confirmation.

Supported examples: “what's on my calendar tomorrow,” “am I free at 9 tonight,” “find emails from NVIDIA,” “open the newest one,” “find my resume in Drive,” “open 1,” “read my HANNI design doc,” “show me recent Google Docs,” “what Google Tasks do I have,” and “what about my school account.”

## Limits and merge assessment

- **NOT_IMPLEMENTED:** Gmail send/reply/delete/archive, Drive delete/share, and Docs editing. Sending needs a reviewed-message confirmation flow absent from the current session. Unsupported writes are not registered or granted scopes.
- Named Calendar mutations and task completion remain blocked in chat; the owner can use exact-ID manual CLI commands with confirmation. This preserves the existing permission boundary.
- Drive opening returns metadata and a URL, without launching a browser. Docs support is native text export only, capped at 6,000 characters with partial status. PDF/Office content and attachments are not downloaded. Searches and threads are bounded.
- Tasks default to `@default`; manual calls may provide a known task-list ID. Generic tasks stay with the existing local todo provider.
- HTTP sessions are short-lived per request. Network timeouts, response limits and refresh limits are enforced. No persistent background Google sync was added.
- Browser consent, organization policy, enabled APIs and real end-to-end account access still need verification after owner login. No live model benchmark was run for this patch.

**Merge assessment:** automated tests and safety gates pass; the implementation is ready for review as an opt-in Google feature. Live account verification remains a deployment/setup check. Review the earlier audio changes independently when preparing a commit.

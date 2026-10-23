# EMAIL CAPABILITY IMPLEMENTATION REPORT

## Architecture and capabilities

Added `email.search` and `email.read` to the existing ToolRegistry. Both use the
existing permission checks, emergency stop, Google Credential Manager vault,
OAuth connection, network timeout, and bounded response handling. Existing
`gmail.search` and `gmail.read` remain available for low-level requests.

The pipeline is: natural-language plan -> registry -> Gmail adapter -> normalized
messages -> local relevance filtering and thread state -> grounded response.
Email responses use deterministic extraction and quoted excerpts. Raw email text
does not choose tools or become model instructions.

The provider protocol exposes account discovery, search, message read and thread
read. `NormalizedEmail` and `EmailActionItem` provide structured source IDs,
timestamps, sender information, status, explicit deadlines and evidence for later
workflows. Future action policy distinguishes local drafts, external communication
and destructive operations. No email write handlers are registered.

## Files changed

- `src/hanni/tools/email_routing.py`: structured plans, intent, local dates,
  source selection, follow-up plan carryover, and disabled write-intent detection.
- `src/hanni/tools/email_provider.py`: provider protocol, normalized messages,
  Gmail GET adapter, thread reads and typed provider errors.
- `src/hanni/tools/email_analysis.py`: relevance, action classification, deadlines,
  current-thread state, credential redaction and extractive responses.
- `src/hanni/tools/email_tools.py`: bounded retrieval and registered capabilities.
- `src/hanni/tools/registry.py`, `capabilities.py`, `capability_metadata.py`:
  registration, family membership and privacy-sensitive read metadata.
- `src/hanni/mcp/host.py`, `session.py`: deterministic routing, execution and
  bounded references for follow-up reads.
- `src/hanni/tools/audit.py`: private email arguments and results are not copied
  into audit logs.
- `src/hanni/evals/email.py`, `evals/email/cases.json`: offline email evaluation.
- `evals/routing/cases.jsonl`, `evals/llm_tools/cases.jsonl`,
  `evals/llm_tools/capability_coverage_v1.jsonl`, `src/hanni/evals/llm_tools.py`:
  registry probes and expandable scenario coverage. The frozen 150-capability
  baseline is preserved.
- `tests/unit/test_email_capability.py`, `tests/evals/test_email_eval.py`:
  new regression and evaluation checks.
- Existing capability-count tests now expect 152 registered capabilities;
  the original 150 model scenarios are retained with four additional probes.

The earlier Calendar patch and local diagnostic reports remain in the worktree.
They were not part of this email task. Nothing was committed or pushed.

## Provider integration and live verification

The Gmail adapter uses read requests only. Gmail's existing readonly scope is
sufficient for message and thread reads. Date searches use epoch seconds because
[Gmail interprets date-string search bounds in Pacific time](https://developers.google.com/workspace/gmail/api/guides/filtering).
Thread bodies use the documented
[threads.get endpoint](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.threads/get).

Live verification used the existing connected account:

- `email.search` successfully searched today's email and returned a message.
- The deliberately small search was correctly reported as `PARTIAL_RESULTS`.
- `email.read` successfully retrieved that message's body and returned `OK`.
- Only success flags, counts and status were printed. Private message content,
  IDs and credentials were not written to this report.

## Search, action and thread behavior

Sender matching considers display name, address, subject and content. Company
names are not hardcoded. Topic queries expand concepts such as temporary/initial
password and laptop/computer setup. Explicit latest requests sort matching mail
by receipt time, including when topic relevance differs.

Unqualified searches begin with 90 days and expand once to 365 days if a complete
search has no match. Recent means 30 days. Today, yesterday, this/last week, since
a named weekday and explicit ISO dates use local timezone bounds. Explicit
ranges are not widened.

Recruiting searches combine multiple recruiting concepts, inspect candidate
bodies and group by account/thread ID. Current text is separated from common
quoted-reply formats. Later completion or rejection evidence suppresses older
assessment requests. Newsletters, acknowledgments and explicit no-action messages
are excluded from pending items. Ambiguous requirements remain possible actions.

Deadlines are extracted only from explicit dates or unambiguous relative day
counts. Date-only deadlines remain dates; vague urgency does not acquire a time.
Every action retains its source message and thread.

Follow-ups retain at most 20 message references for 15 minutes, expire after an
unrelated turn and re-read the source. Company-specific action follow-ups retrieve
the current thread. Raw bodies are not retained in reusable conversation history.

## Security boundaries

- Registered email capabilities are read/search only; no send, reply, forward,
  archive, delete, spam or label modification exists in this patch.
- Direct email turns execute through the registry and do not give email text a
  model tool-selection turn. Excerpts are explicitly email evidence.
- Searches use literal sanitized entities rather than user text as Gmail syntax.
- Provider requests use fixed paths and validated message/thread identifiers.
- Credential values are omitted, including unlabeled values when a subject
  identifies the message as credential mail.
- Audit logs contain private-query/result markers. Debug diagnostics contain
  planning bounds and retrieval/classification counts, not message bodies.
- Provider states distinguish not connected, expired authentication, permission
  denied, provider failure, rate limiting, no results and partial results.

## Tests and evaluation

Added 19 unit checks and one evaluation test. Coverage includes sender/body
matching, recency, progressive expansion, latest ordering, pending applications,
thread completion, explicit/relative/unknown deadlines, source follow-ups,
provider failures, credential omission and malicious email instructions.

Full suite: **589 passed, 3 skipped, 17 subtests passed**. The 20 focused email
checks also passed after the final latest-topic ordering adjustment.

Before this patch, 5 of the 8 sampled mailbox requests selected legacy mail tools;
the application-action, internship-action and company-summary prompts did not.
The reply prompt did not have an explicit disabled-email-action response.

After: all 8 mailbox prompts resolve to the new capability, and the reply prompt
is explicitly blocked. The dedicated email evaluation passed **12/12** scenarios:

| Metric | Passing checks |
| --- | ---: |
| Routing | 12/12 |
| Query plan | 11/11 |
| Retrieval | 11/11 |
| Thread selection | 11/11 |
| Action classification | 4/4 |
| Deadline extraction | 1/1 (two deadline expectations) |
| Grounded answer assertions | 11/11 |
| No-hallucination fixture assertions | 11/11 |
| No unsafe action | 12/12 |

These are finite fixture checks, not a general claim of perfect mailbox accuracy.
Run them with `python -m hanni.evals.email` in the installed environment.

The broader routing corpus passed **1089/1091 (99.82%)**. Its remaining failures
are the same folder-opening and Spotify cases observed before this task:
`REGISTRY-folder.open-2` and `REGISTRY-spotify.play_pause-1`.

## Known limitations

- Topic understanding uses concept expansion and lexical relevance, not an
  embedding index or unrestricted model reasoning. Summaries are extractive.
- Search is bounded to 30 candidates per account and at most 12 selected threads;
  caps, body truncation and provider errors produce partial-result notices.
- Full normalized text is bounded to 10,000 characters. Returned evidence and
  spoken excerpts are smaller. Attachment names are retained, but attachments
  are not downloaded or parsed.
- Thread state uses provider thread IDs. Separate threads for the same application
  are not automatically reconciled. Unusual quoting or indirect completion
  language may need manual review.
- Credential disclosure is intentionally unsupported; the original mailbox
  remains the place to view those values.
- Live verification covered search and one body read. Application-action accuracy
  was verified against synthetic mailbox fixtures, not a manual audit of the
  user's private applications.

Recommended next patch: email draft/reply with explicit confirmation immediately
before any outbound message is sent.

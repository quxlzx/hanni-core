# HANNI EMAIL WORKFLOW PATCH REPORT

## Root causes found

- The deterministic email planner recognized a few action phrases but missed
  synonyms such as "applications I need to finish," company reply requests,
  interview scheduling and verification questions. Those requests fell through
  to model replies about unavailable email access.
- A broad recruiting query looked at only ten recent metadata candidates, so
  interview and deadline mail could be crowded out. "Most recent" was also
  misread as an explicit 30-day window.
- Workflow answers used candidate messages to mark a search successful even
  when classification found no requested action. The conversation stored an
  internal privacy marker that could later be echoed.
- Interview topic ranking accepted social/forum subjects that mentioned an
  interview. Repeated messages within a thread could dominate workflow lists.

## Files changed

| File | Patch |
| --- | --- |
| `src/hanni/tools/email_routing.py` | Workflow intent recognition, job-mail listing, local time ranges and planner diagnostics. |
| `src/hanni/tools/email_analysis.py` | Recruiting metadata ranking, precise workflow evidence, current thread state, deadline carry-forward and concise answers. |
| `src/hanni/tools/email_tools.py` | Targeted Gmail queries, 30-candidate metadata stage, thread deduplication, range filtering and outcome status. |
| `src/hanni/mcp/session.py` | Private history marker handling. |
| `tests/unit/test_email_workflow_reliability.py` | Exact phrase, false-positive, time, deduplication, completion and response regressions. |
| `evals/email/cases.json` | Nine additional end-to-end fixture cases. |

## Routing fixes

Application-action synonyms now map to one workflow. Separate structured
intents cover application deadlines, company reply requests, interview
scheduling and email-address verification. Recruiting-mail lists and the latest
job-application email route to metadata search. Important-mail and ordinary
sender/recent queries retain their earlier metadata-only behavior.

## Temporal fixes

Today, yesterday, this/last week, this month and last seven days resolve to
local start/end times before provider retrieval. Local filtering repeats after
Gmail returns metadata and before workflow classification. "Most recent" now
sorts the default search window newest first; it does not impose a 30-day bound.
Job searches may expand from 90 to 365 days only when an unqualified search has
no result. Explicit windows never expand.

## Workflow and action fixes

Recruiting queries retrieve at most 30 metadata candidates per account for
each search pass. Relevant candidates are deduplicated; at most five selected
threads are read for action, deadline, interview, reply or verification
evidence. Completed and rejected latest thread states suppress older requests.
An active reminder can retain an explicit deadline from an earlier message in
the same thread. Deadline answers require extracted dates; reply, interview and
verification answers require specific request evidence. Phone and login-code
verification do not qualify as email-address verification.

## Deduplication and false positives

`dedupe_email_results` removes repeated message IDs, keeps the newest message
per thread, and collapses near-identical sender/subject/timestamp records only
when a thread ID is unavailable. Different application threads with the same
subject remain separate. Interview topic search penalizes social, forum and
promotional senders and favors recruiting sender/subject evidence; body fallback
cannot restore a social-only interview result.

## Response composition

Workflow status reflects the requested evidence rather than merely finding
candidate messages. Direct email results bypass the generic action ledger, and
the old internal history marker is filtered from model context. Valid answers
do not append "I couldn't verify." Actual partial provider results receive one
brief partial notice. Application actions, deadlines and requests use short
sender-and-action lines; no inferred deadlines or generic "review next steps"
items are emitted.

## Tests added and passed

- New unit regressions cover all ten reported failure patterns, route variants,
  completed threads, near-duplicate records, a reminder with an earlier
  deadline, last-seven-day bounds and the internal marker.
- Full repository suite: **628 passed, 3 skipped, 17 subtests passed**.
- Email evaluation: **27/27 cases passed**. Body policy: **19/19** checks;
  routing: **27/27**; query plans and retrieval: **26/26** each.
- Broader routing benchmark: **1089/1091**. The two failures are the existing
  `REGISTRY-folder.open-2` and `REGISTRY-spotify.play_pause-1` cases.
- A live connected-Gmail adapter run executed the ten exact requested prompt
  shapes. Recent job mail, this-week recruiting mail, important mail and the
  interview topic lookup used metadata only. Workflow queries inspected at
  most five selected full threads. The application-action synonym and original
  phrase produced the same actionable state; no tested answer surfaced the
  old marker or a contradictory failure. The live interview-scheduling query
  found no qualifying recent request, and the deadline query found no explicit
  date among its selected threads. A HANNI dashboard process was not running,
  so the browser conversation itself was not exercised.

## Existing regressions and known limitations

- The two broader routing failures above remain outside this email patch.
- A search pass is bounded to 30 metadata candidates per connected account;
  dense inboxes can hide older matching messages. Five thread reads bound
  workflow content checks. A bounded no-result statement describes the checked
  recent messages, not a claim about the entire mailbox.
- Sender and organization categories are heuristics. A direct recruiter message
  embedded in a generic social-platform notification may be excluded.
- Very long bodies and provider errors can produce partial results. Gmail
  access was tested through the adapter, not through a running browser HANNI
  instance. Restart HANNI to load the patch.

## Recommended next capability

Add source-linked, user-requested expansion for recruiting searches so HANNI
can inspect older pages or a particular thread when the bounded first pass
does not find a requested action.

# Email search precision patch

## Root cause

Sender and topic searches shared a relevance check that accepted company names
in subjects, snippets and bodies. Low metadata relevance could trigger body
retrieval even for ordinary sender lookups. Several recent-mail phrases were
missing from deterministic routing, and the formatter emitted retrieval details
and partial-search warnings for ordinary result caps.

## Implementation and files changed

| File | Change |
| --- | --- |
| `src/hanni/tools/email_routing.py` | Explicit `from`, `about`, `recent`, `workflow` relations; metadata/body policy; recent/date/count routing; organization and important-mail views. |
| `src/hanni/tools/email_analysis.py` | Strict sender evidence, normalized aliases, metadata relevance, conservative action evidence, concise response formats. |
| `src/hanni/tools/email_tools.py` | Sender/subject Gmail queries, local validation, bounded body fallback, metadata-only output and follow-up reads. |
| `src/hanni/mcp/session.py` | Sender-only follow-up matching; metadata-only display versus explicit content reads. |
| `tests/unit/test_email_precision.py` | New regression coverage for the reported false positives, routing, dates, ordering, body budgets and formatting. |
| `tests/unit/test_email_capability.py` | Updated prior expectations and follow-up body-access checks. |
| `src/hanni/evals/email.py` | Sender/subject-aware fixture provider; body-policy and ordered-result assertions. |
| `evals/email/cases.json` | Added the six requested real-failure patterns; updated concise-answer assertions. |
| `evals/llm_tools/capability_coverage_v1.jsonl` | Updated email-read arguments for the metadata-only option. |

### FROM versus ABOUT

FROM queries use Gmail `from:` terms and independently check each result against
sender display name, sender address and domain. Subjects, snippets and bodies
cannot qualify a FROM result. Normalization joins complete adjacent tokens, so
Tik Tok matches TikTok while unrelated substrings do not qualify. The sender
local part also supports third-party recruiting addresses such as
`intel@myworkday.com`.

ABOUT queries search subjects first and rank sender-plus-subject evidence above
subject-only matches. Only when metadata is insufficient can an ABOUT query
inspect up to three candidate message bodies. Basic sender searches never take
this fallback.

### Metadata and body policy

- Recent, sender, organization and important-mail searches retrieve metadata
  only. Their public results contain neither body text nor snippets.
- Explicit requests to read or summarize retrieve the selected message content.
- Workflow questions first select likely recruiting metadata, then inspect at
  most five candidate threads. Weak next-step wording and form receipts do not
  create action items.
- Showing the latest retained result uses metadata; asking what it says reads it.
- Today, yesterday, this/last week and this month use local timezone boundaries.
  Current periods end at now. Latest returns one result; an explicit count is
  honored up to the existing 20-result limit.

### Response formats

Results use sender, quoted subject and a date when useful. Sender checks use a
short Yes or a direct-sender no-match response. Explicit recent counts produce
numbered lists; organization requests list names; important-mail requests return
a few ranked messages. Ordinary result caps do not emit warnings. Actual provider
failures and incomplete requested content still produce one concise notice.

## Verification

- Full repository suite: **608 passed, 3 skipped, 17 subtests passed**.
- Final focused email tests after formatting and follow-up checks: **39 passed**.
- Full email evaluation: **18/18 scenarios passed**, including all six requested
  failure patterns. All **10/10 explicit body-policy assertions** passed.
- Intel, TikTok and NVIDIA fixtures reject Reddit, LinkedIn and unrelated senders,
  even when a broad provider response includes them. Recent queries route to
  email retrieval, and five-most-recent returns exactly five messages newest first.
- Live connected-Gmail verification: all three sender queries returned a direct
  sender match, with **zero full-body calls**. Verification blocked full-message
  and thread reads; no private message contents are included in this report.
- Organization filtering, important-mail ranking, small ABOUT fallback, weak
  action evidence, provider errors and normal result caps also have regressions.

## Remaining limitations

- Sender matching uses header evidence, not sender authentication. Organization
  identification and domain decomposition are conservative heuristics; there is
  no comprehensive alias directory or public-suffix database.
- Retrieval is bounded to at most 30 metadata candidates per account per search
  pass. Unqualified searches begin at 90 days and may expand to 365 days when no
  match is found; explicit dates are never widened. Recent means 30 days.
- ABOUT fallback is lexical, not an embedding search. It may miss concepts that
  require broader paraphrase recognition or bodies outside the candidate budget.
- Existing credential redaction, attachment limitations and extractive content
  responses remain in place. Body retrieval for workflows can include multiple
  messages within each selected thread.
- The broader routing corpus previously had two unrelated failures:
  `REGISTRY-folder.open-2` and `REGISTRY-spotify.play_pause-1`.

Changes are local. Restart the running HANNI process to load them.

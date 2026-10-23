# Tool Intelligence V2

HANNI keeps its original safety, provider, date, history and permission resolvers.
Unresolved reads now have a local statistical metadata index, and weak read menus
can expose a bounded alternative when it shares at least two existing evidence
terms and contributes uncommon additional evidence. Model selection and actual
execution still use the original MCP host and ToolRegistry. This index neither
executes capabilities nor authorizes calls.

`tools/discovery.py` uses field-weighted BM25 and bounded dictionary-derived typo
correction. It indexes names, descriptions, actual registered aliases/tags, argument
descriptions and categories. Legacy phrase-derived hints remain in the original
ranker, but are excluded from this statistical index. Repeated metadata and query
lengths are bounded. No embedding model, package installation, automatic download,
cloud service, query-to-tool table or benchmark answer lookup is required.

Candidate exposure uses distinct matched terms, weighted coverage, relevance floors
and score margins. It never pads to a fixed menu size. Eligible read definitions
are filtered before ranking; writes and tools requiring confirmation cannot enter
this generic read fallback. Original allowlisted action and argument-resolution
paths retain their existing behavior. The original eight-tool ceiling remains.

Conversational reporting verbs and quantifiers are excluded symmetrically from
queries and metadata so their rarity in an alias cannot widen a resolved menu.
Absolute and explicitly relative paths become `file path` in intent/ranking views;
their literal values remain available to the original argument resolvers. An
exact external operation leaf can retrieve a currently approved import only when
it is unique across built-ins/imports and has additional lexical metadata evidence.
Shared names retain ambiguity and original permission filtering.

Indexes and eligibility snapshots invalidate with registry.revision. MCP approval,
tool-list change, disable, removal and schema reapproval therefore invalidate the
new index alongside the existing one. MCP original identifiers, JSON schemas,
definition hashes and execution gates remain unchanged. External descriptions are
bounded untrusted retrieval data, never policy or executable instructions.

## Development evidence

Run from the repository root with the existing development environment:

```powershell
.venv\Scripts\python.exe scripts/check_retrieval_development.py
```

The script compares current source with the original M1 host in commit `ca95b05`.
It uses the same metadata-only registry, synthetic provider availability and fixed
case times. Three warm passes precede five interleaved measured passes. It never
calls a model, capability handler or holdout loader. The original routing evaluator
normally reconstructs a current host during isolation; the script explicitly
retains the baseline host class for its baseline evaluation to prevent that bias.
The historical corpus owner timezones come from the original fixture manifest.
Complete corpus audits also check extra unmocked menus and resolved arguments;
required-tool recall alone is insufficient to establish regression compatibility.

| Development measure | Before | After |
|---|---:|---:|
| Historical routing cases passing | 1129/1131 | 1129/1131 |
| Historical routing mean score | 99.5904 | 99.5727 |
| Historical model-scenario required menu sufficiency | 166/166 | 166/166 |
| Historical no-tool scenario decisions | 28/28 | 28/28 |
| Curated capability probes with required tool | 264/264 | 264/264 |
| Complete historical scenario corpus audit | 194/194 | 194/194 |
| Complete historical capability corpus audit | 264/264 | 264/264 |
| Unfamiliar development required-tool recall | 23/35 (65.71%) | 31/35 (88.57%) |
| Unfamiliar development no-tool decisions | 4/5 | 4/5 |
| Mean candidates across 40 development cases | 0.90 | 1.225 |
| Development retrieval P50 | 0.949 ms | 1.084 ms |
| Development retrieval P95 | 4.368 ms | 4.530 ms |

These exposed development cases are not an independent generalization benchmark.
The historical model-scenario corpus now expands to 194 cases: 166 require a tool
and 28 do not. The separate capability corpus has 264 schema/menu probes, two for
each of 132 model-facing capabilities among 172 registered built-ins. Menu recall
does not establish correct model arguments, execution, or verified task completion.
The sealed final holdout and real local-model comparison belong to independent
verification and are not used for tuning here.

Exploratory alternatives showed that a generic BM25/character top-eight menu could
reach 34/35 unfamiliar tool requests but failed all five no-tool cases. A strict
dynamic prototype reduced its mean menu to 2.45 candidates without fixing that
problem. A 48-dimensional latent metadata projection added no unfamiliar recall.
Those methods are not pretrained semantic embeddings. The selected integration
uses original intent gates and stricter evidence calibration; a more permissive
intermediate implementation was rejected because it degraded existing menus.
The slight historical mean-score decrease comes from additional allowed candidates;
there are no new failed routing cases. This is a reported exposure tradeoff, not a
claim that every retrieval metric improved.

The four remaining development tool failures include interpretation that cannot
be recovered from literal metadata alone. Arbitrary synonym paraphrases remain a
limitation without a separately approved local semantic asset. One original
conversational schedule request still exposes a calendar tool; the implementation
does not claim the aspirational 95% unseen recall target is achieved.
An earlier candidate reached 32/35 but added unmocked tools in two original
capability probes. Generic framing-word filtering restores complete original
corpus compatibility at the cost of that one development recall case.

The host also forwards the existing per-turn correlation ID into ToolRequest, and
marks a raised timeout retryable only for authoritative, explicitly retry-safe,
low-risk built-in reads. External definitions and writes never gain retry authority
from server metadata. The original execution session remains responsible for any
bounded retry, cancellation, deduplication and verification.

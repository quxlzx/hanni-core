# Campaign 5 checkpoints

## Baseline and actual inventory

Starting HEAD: `0aede831853b6876bc8904838a41f7b2ce8f3967`. The existing
Campaign 4 working changes are part of this baseline and remain uncommitted.
Unrelated owner files remain outside campaign changes. Two actual engineers and
an independent verifier are working in separate campaign helper/test paths.

The intelligence engineer archived 36 original files before any repairs:
`data/campaign5-intelligence/original-source/manifest.json`, SHA256
`a676946c12640634a7f96ab09c664d7b3bdf40100039830befdab46b369ed5f6`;
archive SHA256
`4a6ecc26638b1e954186191eef87aa82fff5dea60305f54e1bdbb00732342163`.
The original relevant regression run passed 285/285 tests. Controlled new
intelligence tests initially passed 37/65, and collaboration controls passed
6/8. These are implementation fixtures, not live model quality results.
Independent reproduction and final corpus sealing are required before repairs.

Manager discovery uses original AdaptiveModelEngine, ComputeScheduler and
protected transport, with exact read-only copies of owner deployment/context
files in an isolated registry. No model service or owner process is started or
stopped. `data/campaign5-manager/discovery-initial` records exact source/config
archive and before/after runtime identity. Before/after source manifest SHA256:
`7afe8b250ec1ea22e5fb2c5bdf9d8ae19bc1b919cd8324f016d6219e0ad95e62`;
source archive SHA256:
`0edb8fafc88ce7b9dd0b7b930a39f2349be665ad9f1cb15f86b0bcc20a98f23b`.
Source and copied owner configuration bytes remained unchanged.

Four configured endpoints were dynamically discovered. The local server is
healthy and its actual weights are `Qwen3.5-4B-Q4_K_M.gguf`, SHA256
`25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`.
Its model PID 38832 and HANNI parent PID 46084 were preserved. At admission,
available RAM was 1,833,373,696 bytes, below the original 2 GiB reserve; short
synthetic, tool-selection and synthetic-memory requests were all refused.
Remote Athena P6000/P40 and Wonyoung Strata were unhealthy, with unknown actual
resources and no fresh runtime-bound context/capability evidence. No generation
request occurred. Athena registrations specify `Qwen3.8-27B-Q4_K_S.gguf`,
which differs from the intended IQ3_S models. A configured worker label does
not prove the unavailable worker's actual loaded identity.

Reported local context is 16,384; configured remote limits are 32,768, 32,768
and 8,192. These are not fresh near-limit retrieval proofs. Historical context
measurements remain separate and cannot authorize unhealthy or changed runtime
identities. A second discovery captures native health error details omitted
from the first summary; it does not overwrite initial evidence.

## Prospective corpora and independent pre-repair reproduction

The verifier sealed 100 private tasks at `2026-10-10T09:49:15.610481+00:00`,
ten per requested family, with 10 easy, 60 medium and 30 hard cases. Public
metadata is in `FINAL_SEAL.json`; private author code, prompts and answers are
not inspected by the manager or engineers. Input SHA256:
`5ee4b787856e27a1031a8cdd3e5f753e525579413d1cf25ae65ca6e7b6fb6b34`;
oracle SHA256:
`0cfc00fbf6d1c3eba979ebbd2aae443d617b216ffcd34bd394720d5534a521cc`.

The independent exposed development controls initially passed 1/33 with 32
failures and no fixture errors. A documented prospective-oracle erratum in
`data/campaign5-verifier/implementation-before-v2/ERRATUM.json` distinguishes
an expired lease that can be authentically re-probed from an explicit withdrawal,
and distinguishes new-dispatch queue occupancy from result authorization.
The corrected 34-control suite passed 2/34 against byte-identical original
production. Both original runs remain preserved. These are synthetic boundary
proofs; no hardware/model calls occurred.

Only after sealing and independent reproduction did the manager authorize
narrow repairs to model adaptive placement, collaboration and compute context
proof admission. Cancellation, identity, privacy, current context and resource
guards remain mandatory. Additional model-response identity controls are being
investigated before any wider model-client change is authorized.

The separate 200-task development set is sealed with twenty cases per each of
the same ten families. Inputs:
`evals/models/campaign5_development.json`, SHA256
`d8482a92554913ab24f6836697d694bf61aae4ba80545cc933d0f6d6727a1951`;
separate deterministic oracles:
`evals/models/campaign5_development_oracles.json`, SHA256
`4d53e4d60c019bf247013db990dd88376f4a6c852084a9f5f6b69979b12c832a`.
No response was observed before this seal. Twenty checker/capture contracts
passed, including a bounded disposable coding child and an owned HTTP fixture.
These contract outputs are not substituted for real model outputs. Exact-byte
Git attributes preserve the published JSON seals through future commits.

The second native discovery retained all three worker errors:
`Node SSH is unreachable over the configured LAN and Tailscale paths.`
Local RAM remained below the original reserve. No user action is requested and
no owner service is restarted to work around these blockers.

## Implementation and independent verification cycles

Cycle 1's first engineering focused run passed 96/96. Independent post-repair
controls passed 37/38 and exposed a remaining GPU-device-index-zero reserve
check. That failed run is preserved in
`data/campaign5-verifier/implementation-repair-a`. The next repair enforced
the VRAM requirement for device zero and strengthened delegated cancellation,
context reservation and runtime-bound proof publication. The independent
non-client suite then passed 43/43 in `implementation-repair-b`.

Cycle 2 independently exercised the original local model client through nine
owned HTTP protocol requests: matching/omitted model fields passed, while three
present-but-different model responses were accepted incorrectly. Both engineers
and verifier retained the original 6/9 result before changing the client.
The repair rejects explicit model mismatch and prevents replay after partial
SSE output; compatibility with omitted fields remains. Independent HTTP tests
passed 9/9 after repair. These are protocol fixtures, not local model answers.

Another exposed controlled HTTP test showed that the rejected wrong-model
response polluted the configured model's correctness profile. A separate
independent reproduction preceded the narrow attribution repair. Such errors
now record identity failure and unknown correctness. Genuine task/structured
verification failures keep their existing incorrect-outcome semantics.

The final source-ready engineering focused/affected suite passed **235/235**
in 35.616 s. The broader regression suite passed **356/356** in 111.133 s
before the narrow attribution branch change; affected adaptive/client tests
are included in the final focused run. The final independent implementation
suite passed **53/53**, zero errors/skips, in 9.709 s. These suite counts overlap
and must not be added into a count of distinct scenarios. Evidence and source
hashes are in `data/campaign5-intelligence` and
`data/campaign5-verifier/implementation-source-ready`.

One old Anthropic accounting fixture originally omitted the health timestamp,
reported context and resource adapter required by the repaired admission gate.
Its assertions and cached-input count are unchanged. Its disposable adapter now
declares a truthful controlled 8,448-token allocation for the 8,192-token input
target plus 256-token output reservation; local unknown-resource semantics are
preserved. No owner deployment allocation changes.

An initial relevant-suite invocation named a nonexistent test file, collecting
zero tests. That collection failure and its logs remain preserved and are not
counted as a pass. A separate intermediate 155-case run loaded the original
client before its patch and retained three expected identity failures.

Manager source audit confirms only the four approved adaptive/collaboration/
compute/local-client production files changed. Owner configuration and all
Campaign 4 workflow source bytes remain unchanged; the actual Git index is
untouched. Live collection, whole-input freeze and independent semantic benefit
evaluation still remain outstanding at this implementation checkpoint.

## Whole freeze and completed development collection

The finalized benchmark contract suite passed 31/31. The independent final
implementation/measurement/runner suite passed 61/61, zero errors or skips,
in 10.033 seconds. These fixture counts overlap the earlier checkpoints and
are not model answers. The measurement source seal is
`docs/campaign5/MEASUREMENT_SEAL.json`, SHA256
`a5580d8b7a90a8f755fdafe7c9de620eb7e97e0dba6b07c122e3e48c44ab3757`.

At 2026-10-10 10:17:10 UTC the manager froze all 427 production/configuration/
helper/test/public-input files in `data/campaign5-manager/final-freeze`.
Manifest SHA256:
`10c73380215acfe307906da905daab58570eea5e7e9b7a53ca3938d66ff85e62`;
archive SHA256:
`a822b91e45e6e9a62e090eab737fbeb78d7594049df3e2ea780438452c58d466`.
Both manager and independent verifier checked current membership, exact bytes,
archive members and protected owner configuration. Only derived report metadata
may change after this checkpoint.

The original-native development run completed the sealed 200 inputs in all
six modes, 1,200/1,200 records. Every record was `BLOCKED_NO_INFERENCE`, with
zero generation HTTP, zero actual answers and null semantic/cost metrics.
The manager's structural audit passed and both independent reviewers reproduced
the aggregate from read-only evidence. The earlier six-record pilot is separate
from this denominator. No arm was quarantined or budget-skipped.

After engines closed, the manager froze the actual adaptive-arm development
SQLite file. It has settings 1, decisions 200, proofs 0, measurements 0 and
identity sources 0; SHA256
`0e49eb250a3a1be09076632185b8e661263063e07f6203e802b4a3eda70518d5`.
No proof, model output or profile score was fabricated. Every independent final
case/mode receives a fresh complete copy, preventing final feedback between
requests. The independent collision audit found zero normalized last-user-input
collisions between the 200 public development and 100 private final cases.

## Independent once-only final and closeout

After explicit manager authorization, the verifier ran the untouched final
corpus once through original guarded APIs: 100 cases across six modes,
600/600 records, ten per family per mode. All records were
`BLOCKED_NO_INFERENCE`; actual generation HTTP and semantically observable
answers were both zero. The 115.406-second run measured admission, discovery,
state copies and source checks, not model generation latency. The raw receipt
SHA256 is
`e841249e32a94489fa5d8454161692c4a0b8f2526df8d6d5aa0ac6dc62b72b79`.
All owned stores and transports closed. No final retry, oracle feedback or
held-out tuning occurred.

Strict final requirements include native tool/format proofs and omit the
development legacy-resident exception. For the 500 persisted individual/
adaptive decisions, absent genuine capability/context proofs are explicit.
Resident individual cases also failed the original RAM reserve; each remote
was unhealthy with unknown resources. The 100 selective records fail before
a persisted native decision, so exact per-case exclusions are not invented.
Current remote native-tool transport support is absent. Original capability,
privacy, cancellation and resource guards were not relaxed.

The independent post-run check confirmed the resident PID/create time/command
and parent identity matched initial evidence and its health remained healthy.
Available RAM was 2,042,404,864 bytes, below the original 2-GiB reserve. All 427
frozen files, private seal, development profile and protected configuration
still matched. No owner service was started, stopped or replaced; the Git
index and existing Campaign 4 changes were preserved.

Public closeout artifacts are `REPORT.md`, `DEVELOPMENT_REVIEW.md`,
`INDEPENDENT_REVIEW.md`, `FINAL_HOLDOUT.json` and `VERIFICATION.json`.
Acceptance remains partial: controlled repairs are independently verified,
while real model quality/performance and adaptive/selective benefit remain
unmeasured. Preserve the existing baseline; no speed/ranking/model replacement
is justified. Changes remain uncommitted.

Manager final readback matched 18 independent evidence hashes, validated all
public final mode/family denominators and null quality/cost metrics, and parsed
the four published passing XML suites without failures/errors/skips.
`MANAGER_CLOSEOUT.json` retains that separate result. The final whole-freeze
check and `git diff --check` passed; the actual Git index remains empty.

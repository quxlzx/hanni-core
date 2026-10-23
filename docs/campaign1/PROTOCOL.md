# Campaign 1: HANNI core and routing validation

Baseline: `227a628`, branch `codex/hanni-v3.7-distributed`.

The supplied request references common campaign instructions, but no separate
common-instructions document was found in the repository or attached texts.
This protocol records the applicable user requirements and existing validation
constraints. It does not assume additional authorization to affect owner data.

The manager coordinates integration and final testing. The existing engineering
and independent verification agents are actual Codex agents. The engineer owns
the new development corpus and narrowly scoped routing repairs. The verifier
owns a separate private final corpus, answer oracles, evaluation, failure
reproduction and final review. No other agent roles are simulated.

## Data separation and originality

At least 500 new natural-language requests are required in total. Development
and final requests are independently authored, with capability family,
difficulty, linguistic form, intended disposition, acceptable/required and
forbidden tools, argument predicates, permission expectations and evidence
oracles recorded before observing their routing results. The corpora cover
direct language, paraphrases, slang, misspellings, ambiguity, mixed domains,
multi-tool requests, no-tool requests and real sequential follow-ups.

Novelty checks compare normalized query fields against existing benchmark query
fields without exposing historical holdout answers. Exact uniqueness alone is
insufficient: name or number substitutions and shared templates require review.
The independent verifier freezes final requests and answers with hashes before
any engineering tuning. Final prompts and answers remain private to the
verifier during development. Development failures can be reproduced and used
for repairs. The final corpus runs once after source freeze; subsequent repairs
cannot be presented as a second untouched evaluation on the same corpus.

## Original controller and bounded execution

Every case uses the original interpretation, host routing, candidate menu,
schema preparation, session handling and permission authority. Real model
inference uses the existing local server; no canned reply replaces model output.
Raw transport replies are retained before the original parser, including failed
attempts. Model identity, generation settings, source hashes, request/result
traces, timing and reported usage accompany the run.

The sealed evaluation profile is deterministic and bounded: temperature 0,
top-p 1, output cap 256 tokens, at most three tool rounds, one in-flight request
and no model-routing fallback. This differs from the owner's generation defaults
of temperature 0.35, top-p 0.9 and 768 output tokens. Effective request payloads
must substantiate the evaluation settings; results cannot be described as a
measurement of those production generation defaults. Original transport retries
are recorded separately from model-routing fallback.

The unchanged production permission profile and a separately labelled, narrowly
authorized private-fixture profile have distinct denominators. Only isolated,
reversible file/note/todo operations may execute real action handlers. Foreign
provider, GUI, system power, cluster, credential and communication effects remain
blocked or use controlled result providers after the original authority gates.
Controlled results test controller synthesis and are explicitly labelled; they
do not establish real provider or operating-system execution success.

Original deterministic controller paths are measured as such. When a case has
zero actual controller model calls, a separate diagnostic model selection can
use its original frozen candidate menu without dispatching tools. These probes
are never counted as production controller model selections or as grounded
user-facing controller responses. Actual multi-turn sequences share session and
history state; pre-seeded context tests are separately identified.

This manager-directed execution clarification was recorded before any live
campaign run. The initial sealed execution wording referred to no model
selection; the clarified rule refers to zero model calls. A genuine no-tool
TextSession response supplies real text inference and receives no redundant
selection probe. An empty candidate menu is not a model selection opportunity;
no-tool routing correctness remains distinct from model abstention when choices
are actually offered. Inference admission failures remain end-to-end failures.
The sealed final requests and answer oracles are unchanged.

The existing externally owned local model and application are preserved.
Inference is serial on the single serving slot. No full assistant startup,
microphone, remote service, credential setup, model replacement or owner
configuration change is part of this campaign. Original resource admission,
emergency stop, confirmation and write restrictions remain in force.

## Measurements and failure attribution

Required-tool Recall@K uses annotated eligible tool requirements at configured
menu K=8. Menu sufficiency requires every mandatory tool or an annotated valid
alternative. Forbidden and irrelevant exposure are measured separately.
Tool-selection accuracy is conditional on a sufficient menu, with actual
controller model turns and diagnostic probes reported separately. The report
also retains unconditional end-to-end success so retrieval failures cannot
disappear through conditional scoring.

Argument scores distinguish raw model schema validity, semantic correctness,
conflicts with deterministic fixed arguments, and effective arguments admitted
by the original host. Hallucinated names, inappropriate calls, correct no-tool
decisions, original permission decisions, handler dispatches and unauthorized
executions have explicit counts and eligibility denominators. Grounding checks
compare final controller claims with recorded tool receipts and frozen reference
evidence, including denied, empty and failed results. Failure attribution may
include retrieval, model decision-making, schema handling, execution and response
synthesis; preserving multiple causes is preferable to concealing later faults.

P50 and P95 latency specify case/turn scope, inclusion of errors, and sample size.
Tokens per request use actual server-reported usage where available; missing
usage is reported as missing rather than zero. Transport retries, model calls
and deterministic responses are counted separately. Results are divided by
family, difficulty, linguistic form and execution profile.

Acceptance targets are at least 95% required-tool recall, at least 95% correct
model selection with sufficient menus, at least 98% valid arguments on eligible
cases, zero unauthorized executions, and no critical existing routing regression.
They are targets, not promised or inferred results. Empty denominators do not
pass a target. Repairs require a development reproduction, an architectural
explanation and independent verification. Benchmark phrase special cases are
not acceptable repairs.

## Checkpoints

Each completed implementation and verification cycle records source/corpus
hashes, actual commands and outcomes, open failures and scope limitations.
Existing routing development benchmarks are captured before and after changes;
historical LLM holdouts are not used for tuning. Tests are chosen for affected
controller/routing code. Final reports retain failed and blocked cases and never
convert missing evidence into successful validation.

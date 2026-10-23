# Campaign 1 evidence and reproduction

Run commands from the repository root with the existing virtual environment.
The live runner is deliberately tied to the reviewed external server's PID,
creation time, launcher, command hash and serving flags. If that process changes,
inspect its actual identity before changing an assertion. The runner never
launches, adopts or kills a model process.

## Non-inference checks

```powershell
.venv/Scripts/python.exe -X utf8 scripts/campaign1/manager_inventory.py --output data/campaign1-manager/review-inventory
.venv/Scripts/python.exe -X utf8 scripts/campaign1/manager_regressions.py --output data/campaign1-manager/review-routing --baseline data/campaign1-manager/baseline-routing
.venv/Scripts/python.exe -X utf8 scripts/campaign1/manager_permission_gates.py --output data/campaign1-manager/review-dynamic-gates
.venv/Scripts/python.exe -X utf8 -m pytest -o addopts= -q tests/unit/test_campaign1_routing_regressions.py tests/integration/test_campaign1_recording_boundaries.py
```

Private result directories must be new, and generated state stays under
`data/campaign1-*`. The dynamic gate audit retains original schemas and callbacks
while substituting controlled handlers. Its confirmed placeholder calls do not
execute system commands, alter protected paths or invoke foreign providers.

## Real development inference

After reviewing the harness, use a quiet inference interval on the existing
single-slot model server. Do not run a second live client or a heavy test suite
concurrently.

```powershell
.venv/Scripts/python.exe -X utf8 scripts/campaign1_verification/run.py --corpus evals/campaign1/development.jsonl --output data/campaign1-verifier/review-development --live
.venv/Scripts/python.exe -X utf8 scripts/campaign1_verification/score.py --run data/campaign1-verifier/review-development --corpus evals/campaign1/development.jsonl
```

The default fixture file preserves version 1. To measure the final repaired
contracts with corrected generic dependencies, pass
`--fixture-sources evals/campaign1/fixture-sources-v2.json` to the runner. The
initial development run and its raw replies are immutable historical evidence;
running current code creates a new development result rather than recreating
that earlier source freeze or its model replies.

The raw receipts retain pre-parser replies, actual HTTP generation settings,
model usage, original menus, validation and post-authorization effective
arguments, controller answers, tool results, dispatch scope and cleanup identity.
Controlled facts come from the frozen fixture sources; model answers come from
actual inference. Automatic field matching is a grounding screen. Independent
semantic review is required for grounded-response accuracy.

Development reruns are development evidence. They cannot make a final holdout
untouched again. The independent final corpus is privately sealed, requires an
exact source/config/harness/fixture freeze proof, and has a global once-only
execution claim. Subsets, dry previews and final-case retries are refused. A
source change during final stops further dispatch; remaining cases are untested.

The reviewed final byte snapshot is
`data/campaign1-verifier/final-production-freeze-01/pinned-sources.zip`, SHA-256
`515d8bcb989c6b66848eb35771e23665fb5c59709df78d555ac3b5e1802f8975`.
Its `freeze-proof.json` lists 230 exact source/config/harness/fixture/rubric and
schema-migration members. The Manager independently checked both archive bytes
and current files against all 230 hashes. It contains no final oracle, model
weights or owner data. Final execution uses a fresh private Python cache prefix;
the existing repository bytecode cache is preserved.

Final evaluation uses version 2 directly, retaining version 1 without changes.
The privately sealed final query and oracle file retains SHA-256
`b96221d8fe027ede7cfb1c75c059e50fa664b918cc4a4f092f08855a21174610`.
Do not clear its global execution claim or rerun selected final failures. Once
collected, reproduce aggregate measurements by reading the preserved run:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/campaign1/manager_metrics.py --run data/campaign1-verifier/live-final-01 --output data/campaign1-manager/review-final-metrics.json
```

This command performs no inference or tool dispatch. It checks semantic-review
coverage and hashes while independently aggregating transport usage, latency,
selection, schemas and permissions. Full answer entailment requires the
Verifier's separate review under [SEMANTIC_RUBRIC.md](SEMANTIC_RUBRIC.md).

The acceptance report distinguishes owner policy from additional fixture action
profiles, model proposals from execution, native controller inference from
non-dispatch diagnostic probes, and real handlers from controlled providers.
Inspect failures as well as aggregates; net improvements can hide regressions.

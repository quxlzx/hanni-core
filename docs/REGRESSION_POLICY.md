# Capability regression policy

The 150 registered V1 capabilities are the baseline in
[`capability_snapshot.json`](../evals/routing/capability_snapshot.json). The
baseline names are hash-pinned in `tests/evals/test_regression_policy.py` so
adding a capability to the snapshot cannot silently bypass coverage checks.
This policy prepares future growth; Tool Intelligence V1 is **not yet frozen**
and no V1.1 capability batch has started.

For each newly registered capability, add an implementation test with synthetic
inputs, a validated argument/output schema, a correct risk and permission
classification, at least **two deterministic routing probes**, and at least
**two LLM tool-use scenarios** with mocked results. For sensitive or ambiguous
actions, add a negative scenario showing what stays blocked. Important tools
should have two to five varied LLM cases, including realistic owner phrasing
and result interpretation. A scenario counts toward the automated minimum only
when it requires or explicitly forbids that capability; mentioning it in a
mock menu does not count. The test suite enforces the two-probe and two-scenario
minimum for names added after the pinned baseline. Reviewers must still check
test quality, schema semantics, negative cases, and real execution safety.

Do not edit the locked personal holdout to cover a new tool or to repair a
failure. Add development cases first, audit them without executing capabilities,
then run the chosen model against mocks. Create a fresh blind holdout for a new
freeze decision. Save the corpus hash, routing report, model report, and exact
configuration together. A failing benchmark must remain visible; do not
silently relax an oracle or remove difficult requests.

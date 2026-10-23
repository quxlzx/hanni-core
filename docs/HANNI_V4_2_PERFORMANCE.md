# HANNI V4.2 performance optimization

V4.2 reduces repeated profile and memory work and allows an idle worker to serve
a request while a different worker is busy. It extends the existing model router,
compute scheduler, memory retriever and Model routing screen. The original
workflow controller, MCP tool host, approvals, leases, recovery and process
ownership remain authoritative.

See [implementation checkpoints](HANNI_V4_2_CHECKPOINTS.md), the
[independent benchmark comparison](HANNI_V4_2_BENCHMARK_COMPARISON.md) and
[independent review](v42-reviews/INDEPENDENT_REVIEW.md) for measured outcomes
and the limits of the hardware evidence. Package version is `0.12.0`.

The independent sealed replay reduced controlled idle-worker queue P50 by
77.314%, repeated profile-read P50 by 93.442%, and exact memory-recall P50 by
68.442%. Every profile/context digest matched, and the real primary passed
30/30 cases before and after. These are application-level objectives; retained
server prompt caches prevent attributing the observed model timings to V4.2.

## Profile reads and telemetry

The existing protected routing SQLite database stores bounded numeric
measurements associated with endpoint identity and task category. An
endpoint/identity index and an eight-entry in-process aggregate cache reduce
repeated deserialization of the same history. Temporary measurement triggers
invalidate the cache for inserts, updates and deletions on its own connection;
SQLite `data_version` detects external commits. Quality sample settings are
part of the cache revision. The complete historical quality profile is preserved.
Uncommitted transactions bypass and clear cached aggregates, so rolled-back
evidence cannot be reused by a later transaction with the same trigger counter.

Cached evidence does not authorize dispatch. Model identity, configuration,
capability proofs, health, privacy, resource headroom, current requests and queue
load are rebuilt and checked on each admission. Unknown remote resources still
block dispatch. A cache hit cannot restore withdrawn permissions or a stale
endpoint.

The existing private `/api/model-routing` response adds `performance`, a
bounded descriptive window of the last 100 measurements in one hour, with at
most 32 history slots. It reports P50/P95 response latency, recent failures,
the most recent measured first-content time, processing rates and HANNI queue
wait. Missing observations remain null. No model output, prompt, owner memory,
environment text or credentials are added to performance history.

First-content timing is observed at the client boundary for streaming content;
it includes delays before visible content arrives. Prompt and generation rates
come from actual server phase timings. Nonstreaming remote responses do not
provide first-token timing. Token counts are not divided by whole-request wall
time and relabeled as server generation throughput. Separate backend queue and
network timings remain unknown where the backend does not expose them.
Cancellation explicitly closes the held transport/client generator before
releasing the original inference lease or active slot.

Local GPU readings reuse the original model manager's resource sampling. Remote
readings reuse the original protected resource transport and its ten-second
cache. Successful capture times travel with their samples. The public GPU
observation contains only numeric memory/utilization fields; ambiguous device
matches remain unknown. These observations describe device-wide use and
headroom, not per-model peak allocation or minimum hardware requirements.

## Worker ordering and interactive use

The original queue retains its configured maximum, timeouts, cancellation,
fallback bounds and per-worker concurrency. Within each priority class,
admissions use a sequence allocated under the existing condition lock. This
also fixes FIFO inversions when Windows gives two requests the same clock tick.

A later request can use an idle worker when earlier requests cannot use that
worker. It cannot bypass an earlier compatible request with available capacity.
Compatibility includes the trusted worker assignment, context requirement,
capabilities, sharing categories and capacity reserved for the request class.
Cancelled tickets do not reserve unrelated capacity. Retry and shutdown cleanup
retain the original queue and durable receipt paths.

`ModelRequest.interactive` is a trusted boolean, defaulting to true for existing
foreground callers. Workflow planning and analysis explicitly use false;
background specialist requests inherit that restriction. Remote dispatch passes
the class to the existing scheduler. Reserved interactive slots cannot be
consumed merely because a background analysis uses adaptive routing.

The local primary remains a single nonpreemptive inference slot. Existing
foreground workflow admission gates are preserved; this change does not invent
an additional GPU slot or forcibly interrupt a running pure inference call.

## Current memory and context

Recall reads all applicable current records through one fresh SQLite snapshot
instead of reopening the database for each 500-record page. A bounded
in-process cache of validated lexical terms uses the digest of actual live
content, the privacy-validation boundary and the secret-registry revision.
Secret registration or rotation invalidates previous validation; a privacy
revision change during context construction clears and omits the recalled
context for that call and forces revalidation on the next recall. Records,
source provenance and semantic state are read again on every request. Corrected content with unchanged
timestamps invalidates its prepared terms; deleted and excluded entries leave
the cache on the next recall. No durable memory cache or new execution authority
is introduced.

The existing LAYA relevance scoring, source provenance, exclusions and context
budgets remain in use. Complete records either fit the prompt or are omitted
under the existing budget; V4.2 does not silently truncate facts, schemas or
essential workflow sources. Independent digest comparisons require the full
same selected context and provenance before accepting a retrieval gain.

Configured allocation and tested context capacity remain separate from a
model's claimed architectural maximum. Current placement still uses verified
limits and the conservative UTF-8 byte bound, including actual output/schema
budgets. That bound can reject token-compatible input; V4.2 does not weaken it
based on an approximate tokenizer or expand production allocation to 128K.

## Bounded recent placement

Recent performance can change placement only among endpoints in the same
existing task-quality tier. Ungraded runtime samples do not raise correctness
or authorize a specialist. Manual overrides retain their original behavior.

The fixed policy considers at most 100 same-category, same-identity observations
from the last five minutes. A latency switch requires at least three successful
recent observations and a 20% improvement after the bounded failure penalty.
A 30-second placement hold limits fluctuation. Three consecutive measured
failures cannot establish a speed advantage and can bypass the hold only for a
healthy peer with enough fresh successful observations in that same quality
tier. Missing or expired evidence returns placement to the original default
ordering. Clock rollback cannot extend a hold.
Fresh eligibility remains decisive during a hold.

The history is bounded to 64 trusted requirement combinations and retains no
prompt text. Decisions explain any recent-performance adjustment through the
existing routing receipt. No online training, inferred model expertise,
automatic proof creation or relaxation of resource/sharing policy is added.
This placement behavior is functionally verified using trusted fixture
histories; it has no separately paired end-to-end speed-gain measurement.

## Runtime configuration disposition

The primary weights, Vulkan backend, 16K allocation, q8_0 cache, one server slot
and ownership rules were preserved for reproducible comparisons. P40/P6000
cache formats, kernels, batching and increased concurrency require fresh
authorized hardware evidence. Existing worker configurations and the external
Strata service are preserved. No additional remote warm server, model download,
primary replacement or speculative batching is enabled.

The owned local verifier helper is bounded and must be stopped after the
campaign. Previously owned remote helpers can be stopped only by their original
PID/nonce ownership checks; failed authentication does not justify killing an
unverified process. Private cleanup receipts preserve that distinction.

## Reproducing verification

Run the normal repository regression with the project interpreter and build the
existing frontend with `npm run build`. Focused new behavior is covered by
`tests/unit/test_model_performance.py`,
`tests/unit/test_compute_performance.py`, `tests/unit/test_memory_performance.py`
and the independent
`tests/integration/test_performance_v42_verifier.py`.

`scripts/v42_verification/` contains the sealed protocols, real configured-primary
benchmarks, controlled scheduler/profile benchmarks, exact memory benchmark,
resource inventory, comparison and browser review. Benchmark outputs are private
and must use new destinations under `data/v42-verification`. The independent
report records exact commands, protocol hashes, sample counts and fixture scope.
Re-running only the optimized tree does not recreate the pre-change baseline;
use the recorded baseline commit and the same sealed protocol for a new campaign.

The manager's final package check builds a wheel without downloads:
`python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir data/v42-manager/release`.
`scripts/v42_verification/check_package.py` checks source/static identity,
private-data exclusion, font licensing and imports directly from that archive.
The package verifier requires a new output destination under `data/v42-manager`.

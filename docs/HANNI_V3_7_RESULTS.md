# HANNI V3.7 distributed compute results

The repaired implementation, original workflow execution and native interface
passed independent verification within the boundaries below. The final status is
**PARTIAL**: requested Athena IQ3_S weights are missing, 128K does not fit the
current measured FP16 profile, and the unchanged 4B planner rejected a fresh
complex goal. A real credential logging incident is recorded below.

## Node inventory

All eight nodes passed authenticated read-only discovery through existing Tailscale
SSH. These are availability/inventory results, not a claim that every node hosts an
inference server. Yunjin remains the requested repair placeholder.

| Node | Observed CPU | Observed RAM | Discovery |
| --- | --- | ---: | --- |
| HANNI / Athena | Ryzen 7 7800X3D | 30.01 GiB | PASS |
| Wonyoung | Ryzen 5 2600 | 60.46 GiB | PASS |
| Haerin | Pentium Silver J5005 | 7.08 GiB | PASS |
| Chaewon | Pentium Silver J5005 | 14.94 GiB | PASS |
| Minju | Pentium Silver J5005 | 7.08 GiB | PASS |
| Wonhee | Pentium Silver J5005 | 7.08 GiB | PASS |
| Jeongyeon | Core i5-7500T | 14.99 GiB | PASS |
| Karina | Core i5-7500T | 14.99 GiB | PASS |

Private addresses, interfaces, account identities and ownership receipts remain in
protected local evidence. No model downloads, software installation or service
changes were performed. The default main assistant model was preserved.

## Actual model evidence

Athena's two 24 GiB GPUs have compute capability 6.1 and driver 580.178.04.
The existing llama.cpp build is 0.5.0-dev, build 1, commit `2e7c58c`; its CUDA
library contains sm_61 kernels. CUDA 12.9.86 is installed outside PATH.

The installed Athena model is **Qwen3.8-27B-Q4_K_S.gguf**, 16,363,513,568 bytes,
architecture qwen35. Requested **27B IQ3_S weights were not found**. This is an
explicitly identified alternative quantization, not validation of the requested
file. Metadata declares 262,144 tokens; runtime verification is separate.

| Worker | Verified 8K retrieval | Actual prompt | Generation rate | Measured VRAM |
| --- | --- | ---: | ---: | ---: |
| P6000 | 2/2 exact three-value retrievals | 7,697 tokens each | 12.90–13.07 tokens/s | 15,980 MiB |
| P40 | 2/2 exact three-value retrievals | 7,697 tokens each | 11.72–11.75 tokens/s | 16,026 MiB |

Both model processes were independently matched to the correct GPU UUID and owned
PID. Serving and forwarding bind loopback. Higher context stages are reported
separately from the 8K measurements above.

| Worker | Accepted measured context | Actual near-limit input | Prefill | Generation | Actual 32K VRAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| P6000 | 32,768 tokens | 30,794 twice, uncached | 185.59–186.94 tokens/s | 7.70 tokens/s | 18,762 MiB |
| P40 | 32,768 tokens | 30,794 twice, uncached | 113.03–143.23 tokens/s | 5.32–5.48 tokens/s | 18,758 MiB |

Each worker passed both prospective exact retrieval trials at 8K, 16K and 32K,
with no changed expected answers. The 32K trials ran concurrently on different
GPUs while sharing Athena CPU and memory. P6000 wall times were 174.766 and
175.953 seconds; P40 times were 229.078 and 286.953 seconds. These are workload
measurements, rather than guaranteed general throughput.

The actual model has 16 full-attention layers, four KV heads and K/V widths of
256. FP16 KV therefore needs 65,536 bytes per token. Increasing 32K to 128K
adds 6,144 MiB of KV alone. Holding all currently measured buffers constant
gives minimum total VRAM of 24,906/24,902 MiB, exceeding the GPUs' actual
24,576 MiB before additional compute-buffer growth. **128K was not launched**.
This is a calculated preflight bound, not an executed 128K measurement.
Quantized KV, flash attention and CPU offloading are not certified by these
Pascal FP16 tests; enabling them requires separate compatibility evidence.

Both 64K workers actually loaded on their assigned GPUs, using 22,400/22,394 MiB
with 2,037/2,045 MiB free. Each first prospective retrieval used a prompt measured
at 61,587 tokens, but hit the bounded 300-second HTTP read timeout
(300.015/300.000 seconds). No second request or larger stage followed. Allocation
is not retrieval proof: accepted capacity stays **32,768** for both workers.
This identifies the largest verified capacity under this campaign's budget,
rather than proving a universal physical inability to complete 64K with more time.

Wonyoung's original Strata IQ3_S model consists of two existing shards totaling
83,617,662,656 bytes (approximately 77.88 GiB), architecture qwen4exp. The actual
loaded API reports `qwen3.8-flash-next-iq3_s`. Original model, configuration, server
and launcher hashes were independently preserved. The wrapper's initial virtual
environment interpreter resolution bug was repaired without installing packages.
The corrected startup passed load, authenticated API/model checks and two exact
independent small retrieval requests (8.578 s and 2.687 s). Two independent
near-8K trials exactly retrieved all three ledger values at 7,697 input tokens.
The first took 16.859 seconds; the second took 3.110 seconds with 7,690 cached
input tokens. The original verifier FAIL is preserved: its usage accounting
counted only seven fresh tokens in the second request. Inspection of unchanged
Strata source proved that fresh plus cache-read input is the full context. A
separate accounting erratum passes the original oracle without new inference.
The accepted Strata context is **8,192**, rather than its larger configured
metadata. Its actual small workflow reports measured 24.6–29.7 generated
tokens/s and 99.5–156.3 prefill tokens/s; these are server timings for that
specific short workload.

## Original workflow and concurrency evidence

The final actual GPU cohort uses a disclosed synthetic planner fixture to produce
a reviewed two-analysis plan. Original planning validation, owner approval, exact
file reading, scopes, invocation receipts and completion verification remain active.
Both analysis responses come from the installed model and must calculate the same
source-grounded percentage from `passed=9` and `total=10`. Expected answers were
not changed to match model output.

| Mode | Wall duration | Analysis assignments | Verified outcome | Aggregate completion throughput |
| --- | ---: | --- | --- | ---: |
| Sequential | 18.078 s | P6000, then P6000 | 2/2 analyses; 3/3 workflow steps | 12.17 tokens/s |
| Parallel | 12.766 s | P6000 and P40, overlapping | 2/2 analyses; 3/3 workflow steps | 17.23 tokens/s |

Each cohort generated 220 completion tokens in total. Parallel wall time was
29.4% lower, a 1.416× speedup for this small workload. Parallel admission/queue
delays were 0 and 16 ms; sequential waiting was 0 and 10,484 ms. These are measured
queue delays, not an isolated CPU scheduling-overhead benchmark. Two requests and
one workload are too small to establish a general throughput guarantee. The four
requests reused 0, 0, 624 and 416 cached input tokens. This mixed cache state is
part of the observed result, rather than a cold-cache scaling measurement.

The campaign used an explicit 180-second per-step test budget. Its final requests
finished within the original default 30-second budget as well. Earlier failed
cohorts are preserved: one exceeded the original timeout, and another verified
its first analysis but lost fresh health while the benchmark harness omitted its
health monitor. The final successful cohort adds bounded factual output instructions
and a running health monitor; it does not hide the earlier failures.

The separately verified three-worker campaign preserves that same percentage
oracle with three analyses, all three workers enabled in both modes, and original
controller parallelism limited to one or three reads. The original scheduler
chooses the assignments. All six real responses were independently reconciled
with original steps, invocation records, durable jobs and cited-fact verification.

| Mode | Wall duration | Actual assignment | Verified result | Aggregate completion throughput |
| --- | ---: | --- | --- | ---: |
| Sequential | 39.407 s | Strata, P40, P6000 | 3/3 analyses; 4/4 steps | 8.374 tokens/s |
| Parallel | 10.203 s | P40, Strata, P6000 | 3/3 analyses; 4/4 steps | 32.343 tokens/s |

Both modes generated 330 completion tokens. All three parallel jobs overlapped
for 8.442 seconds. Measured admission/queue delays were 0–16 ms. This is an
observed 3.862 ratio; parallel GPU requests each reused 416 input tokens, while
the other four requests reused zero. It is not a cache-controlled scaling result
or an isolated scheduling CPU-overhead measurement. The disclosed planner fixture
does not establish autonomous complex-goal planning.

Three separately sealed real streaming probes returned their exact ledger values.
Time to first nonempty answer content was 906 ms on P6000, 1,547 ms on P40 and
2,093 ms on Strata; total request time was 2.297/3.063/3.031 seconds. All three
reported zero cached input. These are warm loaded-server client timings and
exclude initial role, empty, keepalive and reasoning deltas.

## Safety and implementation boundaries

The original WorkflowService is the sole execution authority. Distributed work is
limited to supported pure structured evidence analyses. Tool execution and planning
remain local. The other six nodes have verified inventory, without enabling untested
remote job classes or granting models shell access.

The scheduler enforces fresh health, exact model identity, measured context,
capabilities, per-worker categories, known resource pressure, concurrency, queue
limits and original dispatch admission. Memory, screen, sensitive sources and
goal-derived conversation context require separate approval. Canonical Google and
MCP provenance classifier failures were independently reproduced and repaired;
the original failing XML is retained.

Durable jobs and per-attempt events preserve assignments, uncertainty, hashes,
output references, verification, failures and safe reassignment. Restart marks
unfinished jobs for workflow reconciliation rather than replaying actions.
Cancellation rejects late results and respects the original stop/lease/scope
checks. HTTP success alone cannot complete a workflow. Independent late checks
also repaired Windows compute-directory junction escape, auxiliary registry reads
that invalidated live jobs, and context receipts that omitted KV cache settings.
Only original workflow recovery reconciles a genuine crash; reading the registry
does not become a second execution authority. Genuine unchanged FP16 capacity
evidence was explicitly reimported under the corrected runtime fingerprint.

During cleanup, an engineer's broad search of ignored protected raw configuration
echoed the existing Strata API credential into a tool response. It was not
committed or placed into a new public artifact. Diagnostic collection immediately
changed to parsed hash-only reads. The original authentication configuration is
preserved. Credential logging hygiene is **PARTIAL** despite passing functional
permission/privacy/network regressions; this incident is not hidden by test scores.

Current workflow payload/result limits remain unchanged. A server's eventual
128K capability would not mean the workflow payload policy allows all 128K input.
Conservative routing uses serialized input byte bounds plus the output budget.

## Final validation

Independent visible WebView2 review scored Cluster 8.8, Models 8.7 and populated
Workflows 8.8 out of 10; template appearance was 1.0 for each. Nine scoped native
controls passed, including persisted enable/restore, node filtering and selection
reasons. The larger physical screenshot campaign passed 41 relevant checks; its
chat-composer expectation fails because the isolated preview has no chat controller.
Raw failures and that explicit scope limitation remain preserved.

A separate fresh complex benchmark goal used the actual unchanged configured local
4B model, original controller and workflow API, without a planner fixture. It was
blocked after 19.219 seconds: the model returned an invalid bounded plan/binding.
Independent review confirmed invented result paths and invalid artifact/read
binding. No steps, invocations, remote jobs or report were installed. This is a
remaining main-model planning limit, distinct from verified distributed execution.
End-to-end autonomous complex-goal completion is therefore **PARTIAL**.

The final frozen source passed **1,728 tests, two skipped, zero failures/errors**
in 249.924 seconds. All 41 independent compute/security/controller checks passed,
as did the 69 focused repair tests. Frontend TypeScript and production build pass.
The final repaired three-worker native preview passed 11 controls and produced
six physical frames, with no JavaScript or control errors. Existing 8.7–8.8 visual
grades remain above the requested threshold.

One earlier full run failed before an MCP assertion when its released-port
startup probe received its own HTTP request as a status line. A bounded Windows
loopback self-connect reproduction supported that fixture diagnosis; 24 MCP
checks and subsequent full runs passed without production or assertion changes.
The original failing XML remains preserved. Source hashes match the final freeze.

The 64K owned session, prior GPU sessions, temporary local 4B controller, relay
and native preview were closed. No local llama process remains. Independent
Strata cleanup confirms the owned PID/port absent and its original separately
managed process, listener and launcher/server/config hashes preserved. Final
independent GPU cleanup confirms both latest and preceding owned GPU PIDs absent,
loopback inference ports closed, and no NVIDIA compute processes remaining. The
independent report is maintained separately in
`docs/v37-reviews/INDEPENDENT_REVIEW.md`.

## Deliverable record

| # | Deliverable | Implementation and evidence | Status |
| ---: | --- | --- | --- |
| 1 | Updated repository | Local branch `codex/hanni-v3.7-distributed`, M0–M8 checkpoints; no push | PASS |
| 2 | Secure connection manager | Existing strict LAN/Tailscale cluster plus protected roster and compute transport | PASS |
| 3 | Verified inventory | Eight authenticated read-only node censuses; Yunjin repair placeholder | PASS |
| 4 | P40 integration | Actual single-GPU Q4_K_S worker, tested 8K/16K/32K; requested IQ3_S missing | PARTIAL |
| 5 | P6000 integration | Actual independent Q4_K_S worker, tested 8K/16K/32K; requested IQ3_S missing | PARTIAL |
| 6 | Strata adapter | Original IQ3_S model/API, protected authentication, owned bounded lifecycle, actual 8K proof | PASS |
| 7 | Endpoint registry | `src/hanni/compute/registry.py`, protected configuration, actual health/resources and KV-bound receipts | PASS |
| 8 | Scheduler | `src/hanni/compute/scheduler.py`, original analysis dispatch, context/privacy/capability/resource gates | PASS |
| 9 | Recovery | Original workflow leases/checkpoints plus bounded pure-inference retry, cancellation and uncertainty | PASS |
| 10 | Cluster/Models | Existing views extended; independently visible actual diagnostics and safe controls | PASS |
| 11 | Workflow dashboard | Original saved steps plus actual worker assignment, timings, selection reason and verified state | PASS |
| 12 | Model/context benchmarks | Sealed actual 8K/16K/32K and 64K campaign; 128K preflight blocked, not falsely claimed | PARTIAL |
| 13 | Concurrent results | Independently audited three-worker 39.407/10.203 s campaigns with cache disclosure | PASS |
| 14 | Failure/recovery tests | Independent interruption, safe retry, late result, crash/no-replay and genuine reader/junction regressions | PASS |
| 15 | Security results | Functional regressions pass; actual credential tool-output incident disclosed | PARTIAL |
| 16 | Configuration/startup docs | `docs/HANNI_V3_7_DEPLOYMENT.md`, protected settings and original lifecycle | PASS |
| 17 | Reproducible deployment | New-output campaign runners, sealed independent scripts and preserved raw failures | PASS |
| 18 | Independent report | `docs/v37-reviews/INDEPENDENT_REVIEW.md`, separate verifier with no production edits | PASS |

Complex autonomous goal completion remains PARTIAL because the original unchanged
4B model failed the fresh planning/binding test. Controlled dispatch success does
not change that finding. The other six nodes have inventory only; no untested
CPU/inference job classes, services or software were enabled. Private data-sharing
categories remain unapproved in production, and original payload/step limits are
preserved. All raw evidence and deployment values remain in ignored protected data.

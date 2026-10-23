# V4.1 prospective evaluation

Multi-model benefit is **not demonstrated in this run**. The original 4B baseline and a live routine regression completed, but fresh Athena SSH authentication/connectivity and resource observations failed before any paired collaboration response. The protected resource admission rules were retained. Automatic collaboration remains disabled without qualifying paired evidence.

## Sealed scope and fairness

The independent verifier defined 16 synthetic cases, two in each requested category, and deterministic oracles before any model response. The protocol SHA256 is `95969febedfa24233c4dc23cd454658c03354c11bf98910b3756f1cd18f54818`.

Categories cover coding analysis, benchmark interpretation, document comparison, tool-result reasoning, planning, long-context synthesis, conflicting evidence, and failed-model recovery. Prompts contain synthetic source data, with no private memory, credentials, screen contents, or user documents. Models never receive expected answers. Exact source/oracle checks determine correctness; agreement earns no credit.

The first measured baseline uses the original configured `Qwen3.5-4B-Q4_K_M.gguf`, API alias `supervisor`, temperature 0, JSON-object output, 384 output tokens, and one inference per case. It is a fixed-primary baseline, not V4's already available bounded sequential verification fallback.

To make that distinction explicit, a supplementary paired protocol was sealed after this initial baseline and before any further complex-model calls. Its SHA256 is `f5556b8a618ab0f9b7c5125595ba55fdb6823cfbfcafb42cadf13ebecfdbd95a`. It keeps the same 16 prompts and oracles and compares:

- Fixed primary, zero fallbacks, with the same trusted validator.
- Existing V4 sequential routing, at most two fallbacks, with that validator.
- V4.1 explicit parallel analysis, at most three participants and concurrency two, with that validator.

These are repeat cases, not a newly unseen cohort. This paired campaign produced **zero complex inference calls**: an authorized SSH preflight failed. No comparative gain, extra-token total, GPU consumption, or recovery benchmark is fabricated from the absent paired results.

## Real fixed-primary results

All 16 baseline responses came from the actual original primary. There were no transport failures.

| Predefined category | Exact verified outcomes |
| --- | ---: |
| Coding analysis | 0 / 2 |
| Benchmark interpretation | 1 / 2 |
| Document comparison | 1 / 2 |
| Tool-result reasoning | 1 / 2 |
| Planning | 0 / 2 |
| Long-context synthesis | 1 / 2 |
| Conflicting evidence | 2 / 2 |
| Failed-model recovery task answers | 1 / 2 |
| Total | **7 / 16** |

Median response latency was **401.853 ms**, total inference response time **7,376.256 ms**, and the server reported **313 generated tokens**. Local loading, weight hashing, and preflight inspection are outside these inference timings. The baseline recovery rows assess their task answers only: a single model has no secondary failure to recover from.

A separately disclosed position-aware output metric matched **43 of 65 expected atomic fields/elements**. Of 61 returned atomic claims, **18 disagreed with or were absent from the sealed expected output**; four expected claims were missing. Array positions matter, so a wrong required ordering counts as an unsupported positional claim. This deterministic metric is not a general hallucination-rate estimate.

Important observed weaknesses included incorrect code ordering, failure to pool benchmark denominators, wrong memory-unit arithmetic, wrong graph cost despite a correct path, truncated dependency ordering, and wrong synthesis sums. The two conflict-evidence cases correctly rejected unsupported majority/cached evidence. Two examples per category are insufficient to certify model quality.

## Real routine regression

Five simple synthetic stored-value lookups were predefined in the supplementary protocol. Each ran through a pinned primary and through the production automatic collaboration policy, using the same prompt/output settings. Both paths verified **5 / 5** outcomes, each used exactly one participant, and the observer recorded **zero remote transport calls**.

Median latency was **251.647 ms** for the fixed path and **212.852 ms** for automatic policy. Fixed always ran first, including first-request cache warmup. This small ordered sample supports no observed routine regression, not a speedup claim. Remotes were registered but currently unavailable with unknown resources; controlled security tests separately verify that available secondary endpoints also remain unused for routine automatic requests.

## Resource and recovery limits

The initial baseline recorded actual local host RAM and best-effort device memory snapshots. These are capacity/residency observations, not isolated peak process allocations, minimum hardware requirements, or energy measurements.

The paired runner was prepared to sample actual Athena GPU total/used VRAM and utilization at one-second intervals plus command duration, including shared loaded residency in every mode. Fresh read-only SSH sampling was unavailable, so **paired GPU consumption, utilization, overhead and energy remain unknown**. Existing authenticated HTTP forwarding connections still answered readiness checks, but HTTP readiness does not supply fresh RAM/VRAM or grant resource admission.

Independent controlled tests cover unavailable/timeout/invalid secondaries, cancellation, withdrawn admission, identity mismatches, unknown resources, private context, and advisory reviews. Those scripted tests are recovery/security evidence, not live model-performance benchmarks.

The local verifier-owned primary was stopped and its exit verified. Nonce-checked cleanup of the temporary P40 and P6000 servers failed because fresh authorized SSH remained unavailable. Their existing owned HTTP forwards still returned `status=ok` after the stop attempt; **the remote servers may remain running**. Private PID/nonce ownership receipts are retained for safe reconciliation using `scripts/v41_verification/cleanup_owned.py`. No unrelated server was targeted, and the original Wonyoung Strata service was not changed. The diagnostic Strata endpoint was unavailable and was not started.

Future GPU helpers attempt an independent finite remote expiry guardian immediately after an owned startup, checking the exact PID and ownership nonce before termination. Ownership receipts are saved before that attempt. **Installation is a separate fresh SSH request, so authentication loss between startup and installation remains a gap; the helper does not guarantee remote expiry or cleanup.** An atomic startup/guardian operation would be needed to remove that gap. The attempted-guardian source improvement was not retroactively installed on the already running helpers because authentication was unavailable. Their shutdown is not claimed.

## Reproduction artifacts

Verifier scripts are under `scripts/v41_verification/`. Private responses/proofs remain under `data/v41-verification/`; they are excluded from packages and public documentation. Source protocols can be regenerated with `sealed_protocol.py`; the paired runner depends on existing independently measured protected V4 identity/capability/context evidence and preauthorized deployment. It never downloads weights or changes the primary.

The actual acceptance blocker is a missing live paired comparison with demonstrated improvement in at least one predefined complex category. There is no basis to enable automatic collaboration or recommend replacing the primary from this campaign.

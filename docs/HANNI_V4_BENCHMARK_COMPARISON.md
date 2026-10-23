# V4.0 benchmark comparison

These October 9, 2026 measurements use actual existing inference endpoints and
synthetic inputs. The independent verifier sealed six held-out cases and two
development cases before inference. Only the development results informed the
prospective adaptive cohort. Model settings, prompt hashes, outputs, graders and
owned serving-session receipts are retained in protected ignored
`data/v40-verification`; no credentials or user conversation were evaluated.

## Fixed-model holdout

Each endpoint received the same six held-out requests. Answers were checked
against the same external exact oracle. HTTP success and valid JSON alone did
not count as a correct task. The table shows median response and reported token
rates for this short-answer workload, with temperature zero, thinking disabled
and an output limit of 384 tokens. These rates are not universal hardware claims.

| Actual endpoint/model | Correct tasks | Median response | Median generation | Median prompt processing | Tested context |
| --- | --- | --- | --- | --- | --- |
| Resident Qwen3.5 4B Q4_K_M | 2/6 (33.3%) | 0.280 s | 83.33 tokens/s | 775.51 tokens/s | 16,384 |
| P40: Qwen3.8-27B-Q4_K_S.gguf | 3/6 (50%) | 2.690 s | 14.44 tokens/s | 72.68 tokens/s | 32,768 |
| P6000: Qwen3.8-27B-Q4_K_S.gguf | 3/6 (50%) | 1.828 s | 15.90 tokens/s | 143.01 tokens/s | 32,768 |
| Strata: qwen3.8-flash-next-iq3_s | 2/6 (33.3%) | 3.572 s | 22.30 tokens/s | 42.95 tokens/s | 8,192 |

All 24 held-out fixed-model calls returned successfully. Correctness remains low,
and six cases per model do not establish a reliable general ranking. Different
answer lengths and prompt-cache states affect rate and wall-time comparisons.

The requested custom `HANNI-4B-v0-Q4_K_M.gguf` could not load: the existing file
lacks required tensor `blk.32.attn_norm.weight`. No accuracy is assigned to that
load failure. It remains a separate unconfigured candidate. The requested GPU
27B IQ3_S files were unavailable; the tested installed GPU weights are Q4_K_S.
The primary model was not changed or repaired by modifying training/model files.

## Context and format probes

Counted near-limit retrieval returned three exact values from separated positions:
15,076 actual input tokens at the local 16K profile, 30,836 on each 32K GPU
profile, and 7,723 on Strata's 8K profile. These are successful current-runtime
trials. Prior V3.7 measurements are separate evidence.

The first current GPU context trial retrieved the values but wrapped its answer
in Markdown, failing the sealed strict JSON grader. That failure remains in the
evidence. A separately sealed cycle using the supported JSON-object output format
passed on all three remote workers. The successful GPU cycle took about 231 s on
P40 and 168 s on P6000; Strata took about 15.4 s at 8K. Near-limit prompt work is
substantially different from the short-answer benchmark above.

One JSON-object and one schema-valid native function-call probe passed on each
of four endpoints. A single successful probe establishes the observed format,
not reliable general tool selection. The existing remote compute transport
permits pure analysis, so native remote function-call discovery does not grant
HANNI remote tool-generation authority. Vision and JSON-schema generation remain
unverified unless supported by a separate receipt. No endpoint is advertised as
stable at 90K or 128K.

## Adaptive comparison

The initial prospective adaptive cohort passed 3/6 checks versus the fixed
resident model's 2/6. A verified retry on P6000 rescued the queue-order task.
Posterior reasoning, graph analysis and a coding case failed all three bounded
inference attempts. Those failures took 4.5–6.2 seconds, compared with under
0.5 seconds for the fixed local short answers. The two already-correct local
tasks stayed local; there is no demonstrated meaningful simple-task speed gain.

The original MCP controller also completed a real local CPU/RAM read and a
synthetic file read in both fixed and adaptive modes: 2/2 tasks in each mode,
4/4 correct tool selections and 4/4 verified original execution receipts.
Observed response times were about 1.72/2.37 seconds fixed and 1.71/2.40 seconds
adaptive. These closely matched results do not establish a latency improvement.

The final strong-identity recheck again passed 3/6. Median adaptive response was
3.794 seconds versus 0.280 seconds fixed; one of four requests needing fallback
was rescued. The independent controlled matrix passed 48/48 valid selections or
correct refusals, with zero tested privacy violations or context overclaims.
The final independent suite passed 73/73 checks. These controlled results are separate
from live reasoning accuracy.
A repeated sealed holdout is labeled a regression recheck, not newly unseen.
Held-out measurements are published to production profiles only after adaptive
choices are sealed, and remain explicitly limited samples.

## Resource interpretation and recommendation

The GPU GGUF file occupies 16,363,513,568 bytes. Strata's two existing IQ3_S
shards total 83,617,662,656 bytes. File sizes are disk footprints, not minimum RAM
or VRAM requirements. At the tested local 16K/q8 profile, observed Vulkan model allocation was
2,571.63 MiB, KV cache 272 MiB, recurrent state 50.25 MiB and compute buffer
85.28 MiB; process RSS after retrieval was about 4.45 GiB. The 24-GiB GPUs each
used about 18.4 GiB at the tested 32K/f16 profile. Strata had about 8.97 GiB RAM
and 293 MiB VRAM free at its sampled 8K profile. These are workload observations; isolated minimum serving-memory requirements were not measured.
HANNI therefore displays those requirements as unknown, separately from configured
budgets. Concurrent workloads and a different context/KV profile require fresh
capacity checks.

Retain the resident 4B for existing private local work. P6000 is a measured
synthetic-analysis fallback candidate on these tasks, with lower response times
than P40 and the same holdout score. Neither GPU nor Strata has enough evidence
to become a generally preferred autonomous model, and remote workers currently
authorize synthetic data only. The selector's conservative accuracy threshold
prevents this small cohort from authorizing a broad automatic quality promotion.
No model download or main-model replacement occurred.

See [usage and continuation](HANNI_V4_ADAPTIVE_MODELS.md),
[checkpoints](HANNI_V4_CHECKPOINTS.md), and the [independent V4 review](v40-reviews/INDEPENDENT_REVIEW.md) for final
regression, permission, cleanup and evidence limitations.

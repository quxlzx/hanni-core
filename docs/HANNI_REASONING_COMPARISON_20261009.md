# HANNI inference-worker reasoning comparison

Completed October 9, 2026. Six real inference requests: the same three-problem packet on each worker, repeated once without changing the prompt or expected answers.

**Recommendation: prefer the P6000 running the installed Qwen3.8-27B-Q4_K_S model for workflows whose outputs can be checked deterministically. None of the tested deployments passed enough of this packet to recommend unattended, unverified reasoning.** The P40 is a second worker running the same model. Wonyoung Strata generated tokens faster, but its structured answers were less reliable in this test. HANNI's main model and deployment priorities were not changed.

All three workers were registered but stopped when checked. Bounded temporary sessions were started for the comparison, and each request required a healthy endpoint reporting the exact registered model, verified context capacity, and sufficient observed memory reserves.

| Worker | Actual installed model | Previously measured context capacity | Correct tasks, run 1 / run 2 | Total correct tasks |
| --- | --- | ---: | ---: | ---: |
| P40 | `Qwen3.8-27B-Q4_K_S.gguf` | 32,768 tokens | 1/3 / 1/3 | 2/6 |
| P6000 | `Qwen3.8-27B-Q4_K_S.gguf` | 32,768 tokens | 1/3 / 1/3 | 2/6 |
| Wonyoung Strata | Endpoint model ID `qwen3.8-flash-next-iq3_s` | 8,192 tokens | 0/3 / 0/3 | 0/6 |

The GPU workers used the same installed 27B Q4_K_S model, rather than the originally proposed IQ3_S model. Strata used its existing IQ3_S deployment. Names in this report identify the loaded deployments; they are not independent claims about model provenance or parameter counts.

| Worker | First response | Repeated-prompt response | Generation speed, first / repeat | First uncached prompt processing |
| --- | ---: | ---: | ---: | ---: |
| P40 | 36.721 s | 34.041 s | 14.16 / 14.17 tokens/s | 183.82 tokens/s |
| P6000 | 32.806 s | 30.698 s | 15.64 / 15.57 tokens/s | 239.92 tokens/s |
| Wonyoung Strata | 34.708 s | 10.769 s | 30.5 / 32.0 tokens/s | 77.3 tokens/s |

Response time is client wall time from immediately before the inference request until the complete response arrives. It includes transport and inference, but excludes model startup and preflight health/resource checks. Generation and prompt-processing rates are the servers' native reported timings. Requests were non-streaming, so time to first token was not measured.

Each request had 583 reported prompt tokens. On the repeat, the GPU workers reused 579 cached tokens and Strata reused 576. GPU answers were 473 output tokens on both runs. Strata produced 823 tokens initially and 330 on the repeat. Its faster second response reflects both cache reuse and a much shorter answer; that latency improvement cannot be attributed entirely to cache or faster processing. P6000 generated the identical-length GPU answers about 10% faster than P40.

The three checks tested resource-constrained scheduling, exact conditional probability, and logical entailment with a complete counterexample. Each task earned one point only if its structured answer was correct. Correct prose did not override contradictory numeric fields, because workflow tools consume those fields.

| Check | Correct answer | P40 and P6000, both runs | Strata |
| --- | --- | --- | --- |
| Scheduling | Minimum 18 minutes; starts A=0, B=0, C=4, D=9, E=9, F=16 | Reported 22 minutes and F=13, before dependency D finishes at 16 | Reported 16 minutes and F=13 in both runs; initial prose eventually derived 18 but retained the wrong fields |
| Probability | Reduced posterior `135/329`, approximately 41.03% | Numeric fields said `15/17`; prose eventually derived `135/329` | Numeric fields said `27/107`, then `27/157`; prose derived `135/329` |
| Logic | `not_entailed`, with a complete world satisfying every premise | Correct verdict and valid two-run counterexample | Correct verdict, but only one run; the counterexample omitted the required verified benchmark run |

The scheduling optimum was determined before inference by exhaustive enumeration of valid task orders. It also has a simple lower bound: the GPU tasks require 16 minutes in total, and the final two-minute CPU task must wait for both GPU branches. The witness above achieves 18. The probability oracle used exact rational arithmetic. Logic grading evaluated every premise and the negated conclusion directly against the supplied finite world.

The P6000 recommendation is conditional on verification: it matched P40's answers with lower response times and faster prompt processing. P40 remains useful as another execution worker, but this test supplies no evidence of a different reasoning capability. Strata's roughly doubled generation throughput did not compensate for its invalid final answers and changing probability fields. No worker completed the entire packet correctly in either run.

This is a small test of three synthetic problems, not a broad ranking of the underlying models. Temperature was zero, the output limit was 1,024 tokens, and `enable_thinking=false` was requested to match the current distributed inference profile. No constrained JSON grammar was applied. All six requests returned normally; the failures were answer-quality failures rather than unavailable endpoints, malformed JSON, or truncated responses. A different reasoning profile would require a separate evaluation.

Execution used HANNI's real `ComputeRegistry` and `InferenceTransport`, with synthetic-only authorization. This was a controlled comparison, not a claim that HANNI's local planner autonomously completed a `WorkflowService` goal. The current distributed workflow verifier's supported cited-arithmetic scope was not expanded by this test.

Private evidence is preserved in `data/v37-manager/reasoning-comparison-20261009/`: sealed `protocol.json`, `protocol.sha256`, full `results.json`, and GPU/Strata cleanup inspections. The protocol SHA-256 is `f06dae4faf2ed29d1894d1ab56f4d8cb4aa00ce2f4fba2b14ddb2fb26a3744ee`. All six records have the same prompt hash and protocol hash, and all returned model IDs match their preflight health checks. Grading was local and deterministic; no separate agent review was performed for this comparison. The executed benchmark source is `scripts/v37_campaign/reasoning_compare.py`, which refuses to overwrite the sealed campaign.

Cleanup was verified through read-only remote inspections: all three temporary model processes exited, their serving ports closed, and no GPU compute processes remained. Wonyoung's pre-existing Python service and its port remained active. Whole-file hashes of the original Strata configuration, launch script, and server source matched the prior cleanup baseline. No primary-model switch was made.

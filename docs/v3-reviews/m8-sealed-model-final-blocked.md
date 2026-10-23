# M8 once-only sealed configured-model evaluation

**BLOCKED: the real configured llama.cpp runtime rejects the original planning response schema before generation. Model planning quality, semantic argument accuracy and actual-model task-completion quality are NOT TESTED.** The eighteen sealed cases were consumed exactly once after the final source freeze. No response was repaired, substituted, rerun or used to tune a production feature. This report preserves the blocker rather than presenting failed runtime requests as model reasoning errors.

## Protocol and actual runtime

The eighteen cases and their embedded oracles were sealed before V3 development, with raw SHA-256 `5c839ed7e406d6fbc77384be0c4698100bdbf1316d95c21ca4f95e7ffa445758`. Their contents were not disclosed to implementation agents before execution. The original goals were retained; the evaluator added only actual owned fixture locations and availability context, not expected answers or prescribed tool choices. All fixtures used isolated stores and files. The original Service, host, registry, authority and handlers were the sole possible execution path.

Coordinator GO followed native acceptance and checkpoint `898c8aaa19b35ef69d117dd35578ddb690b81d73`. The raw 198-file public source/config/frontend/executable manifest was `b150518459455724b7f6ff8a875718832befa208b245fbdff075764da95fea8f` before and after evaluation. It excludes credentials, private stores, weights and evaluation inputs; those inputs are pinned separately. Runtime and sealed input bytes remained unchanged.

The original ModelManager started its own llama-server process, PID 25824, on a fresh loopback endpoint. It used the existing Qwen3.5-4B-Q4_K_M GGUF, 2,707,513,696 bytes, SHA-256 `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`. No download or cloud fallback was permitted. The server is build 10679 (`50f068fff`, Windows x86_64). Its log records Intel Core i7-14650HX, approximately 32 GiB RAM, and NVIDIA RTX 5060 Laptop GPU, selected as Vulkan1; 33/33 layers were offloaded. Context remained 16384, parallelism one, requested GPU layers 99, and original KV/manager settings were retained.

The original LlamaCppClient had one request attempt. The production planner's actual overrides were temperature 0 and maximum 3072 tokens. Configured ordinary-chat sampling remains temperature 0.35/max768/top_p0.9; this was not falsely substituted for the planner's call settings. No analysis call occurred (its production override would have been temperature0/max2048). Startup took 9628.01 ms and is separate from per-case timers.

## Observed failure and denominators

| Observation | Count / scope |
| --- | --- |
| Actual original runtime planning requests | 18, one per sealed case |
| Successful generated responses | 0 |
| Requests failing before generation | 18, each `ModelUnavailableError` |
| Compiled plans | 0/18 attempted runtime requests; **not a semantic accuracy score** |
| Workflows safely returned Blocked | 18/18 |
| Binding-pass or analysis calls | 0 |
| Compiled/executed workflow steps | 0 |
| Owner execution-approval controls issued | 0 |
| Positive objective oracles checked against absent output | 11, none established |
| Positive objectives actually executed | 0; completion-quality denominator unavailable |
| Counterfactual/provider execution oracles | 7 NOT TESTED; their immutable fixtures lack the concrete fault/feed/provider interface required to establish those outcomes |
| Inference selection, semantic arguments, goal quality | **NOT TESTED**, because no model response was generated |
| Permission-violation rate | **NOT MEASURED**, zero workflow dispatch exposures; zero effects is not proof of successful instruction resistance |

The persisted case rows retain eleven FAIL outcome assertions and seven NOT TESTED outcomes. Those FAIL assertions mean the requested files/facts/outcomes were absent. They do not mean eleven model answers were evaluated: there were no generated answers. The missing concrete interfaces on seven cases were identified and disclosed before evaluation; they were not rewritten or credited as safe counterfactual success. Statistical model-quality intervals cannot be derived from this run. All eighteen requests share one compatibility failure, so treating them as independent intelligence trials would be misleading.

During subsequent public-smoke preparation, source inspection found an additional unexercised evaluator limitation: its pending action lookup uses approval kind `step`, while the actual Service contract uses `action`. No sealed workflow reached that lookup because all requests failed before compilation; it did not cause the observed runtime rejection. The consumed evaluator remains immutable. This limitation independently prevents claiming that the sealed adapter's unexercised positive execution path was fully validated. The separate public smoke uses the real `action` contract and exact approval bindings.

The authoritative server log reports: `number of rules that are going to be repeated multiplied by the new repetition exceeds sane defaults`, followed by `Failed to initialize samplers: failed to parse grammar`. The error appears eighteen times before any slot completes generation. The failing original response-format name is `hanni_workflow_plan`, using OUTLINE_SCHEMA. Its nested generated grammar includes up to sixteen steps, up to eight criteria per step, bounded 2000-character descriptions and 512-character criteria paths. These are observed grammar/schema features; the exact minimum cause was not isolated by a forbidden rerun. This is a production response-format/runtime compatibility defect, not a harness substitute, insufficient cached weights, download failure or model-quality judgment.

## Timing, cleanup and scope

| Timer | n | Mean | P50 | P95 |
| --- | ---: | ---: | ---: | ---: |
| Failed original runtime request/rejection | 18 | 36.09 ms | 35.94 ms | 45.81 ms |
| Owned fixture setup plus planning/block observation | 18 | 189.16 ms | 187.17 ms | 201.28 ms |
| Owned setup plus full observed case/cleanup | 18 | 202.63 ms | 202.81 ms | 218.32 ms |

P50 is the median and P95 nearest rank. These measure rapid rejection and setup, **not successful inference speed, first-token timing or time to a verified goal**. Positive verified workflow duration, inference throughput and human approval latency remain NOT MEASURED. The raw evaluator field `planning_inference_ms` sums complete original failed requests; its name must not be interpreted as proof of generated-token inference. No repeat or quiet paired causal comparison was performed.

The adapter closed only its owned model process, and PID 25824 was confirmed absent afterwards. All isolated service/fixture resources were closed. No production assistant, SSH, node power, provider operation, arbitrary executable, voice capture or user-data mutation was performed. Original fixture setup may create owned task/file inputs; it is not counted as a model-selected workflow action.

## Preserved evidence and immutable reproducibility

Raw evidence is `data/hanni-v3-review/sealed-model-final/results.json`, per-case JSON, `ONCE_ONLY_STARTED.json`, and `model-state/dashboard-supervisor.log`. Result SHA-256 is `dc28ef9d9928226a6808499a1f0e451f4586e6e22d83f48528b9767b321d10c0`. `summary.json` is a report-only projection; the raw evaluator rows and inputs are unchanged. The exact evaluator SHA is `67a4739bbcec053d8292866cf76bb8b1dbb929545f166717485e82199dd7d73b`. Its generic dependency hashes are model adapter `66533ab5045a5b7c60d4fc07e8db8fa5a74b1fbd1a6e73725f75e4d1d7f91b1b` and service fixture `3b985035d0d5ce913880433159fc57c592455dca3c9eaa5c948d8c8c3ea0ac37`.

Immutable case/oracle, evaluator and settings copies were prepared only after evaluation. They must not be read by implementation agents during a generic compatibility repair, and these eighteen cases must never be rerun as a fresh holdout. Once finally published, they are exposed development material; future quality claims require genuinely new cases. A repaired runtime can be checked on already-public engineering goals under a separate source freeze, without converting this consumed blocked run into an unseen quality PASS.

The independent native interface remains accepted at 8.82/10 with 206 native checks. Engineering safety/core scripted cases and the preserved original 40+4 cohort have their own successful denominators and remain valid for their explicit scopes. They do not remove this actual-model functionality blocker or establish the requested general completion target.

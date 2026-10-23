# HANNI V3.7 independent verification

Independent review verifies actual bounded cluster inference, original-controller workflow execution, placement/privacy gates, and existing native Cluster, Models and Workflows views. All 41 independent controlled checks passed after concrete privacy, storage, recovery and runtime-proof repairs. Overall requested capability validation is **PARTIAL**: the requested GPU quantization is unavailable, 64K retrieval exceeds the bounded request budget, the current 128K profile fails memory preflight, fresh primary-model planning is blocked, and an actual credential-logging incident remains recorded.

The prospective protocol was sealed before model outputs, SHA-256 `1712c95f1132c1bf25fbf3dfbd24f581f88c328e9fa32b6a312780af9c266eb3`. It defines twenty invariants, three exact retrieval values at separated document positions, two repetitions, actual near-limit tokenizer/runtime counts, and staged context growth. Answers were never changed after outputs.

## Independently observed hardware and software

| Resource | Actual evidence | Claim boundary |
| --- | --- | --- |
| Athena P6000 and P40 | Separate 24,576 MiB GPUs, compute capability 6.1, driver 580.178.04; actual device UUID/process associations during inference | Two actual GPU workers |
| Athena backend | Existing llama-server 0.5.0-dev, build 1, commit 2e7c58c lists both devices; CUDA library contains sm_61 kernels; nvcc 12.9.86 | Compatible execution was subsequently measured |
| Athena model | Existing 27B qwen35 GGUF, file type 14, 16,363,513,568 bytes; native-context metadata 262,144 | **Q4_K_S alternate**. Requested 27B IQ3_S was not found. No download or requantization occurred |
| Wonyoung | Ryzen 5 2600, 60.46 GiB RAM, measured AMD vendor/device, 17,095,983,104 bytes VRAM | Marketing board name is not inferred from PCI identifiers |
| Wonyoung Strata | Existing qwen4exp two-shard GGUF, file type 26, total 83,617,662,656 bytes; actual loaded model matches original IQ3_S configuration | Original model, tokenizer and quantization reused |

File types 14 and 26 are Q4_K_S and IQ3_S in the [upstream llama.cpp enum](https://github.com/ggml-org/llama.cpp/blob/master/include/llama.h). Native-context metadata does not prove runtime capacity.

Existing Strata implements actual OpenAI completions/models/properties/health and Anthropic messages/token counting. Bounded owned sessions explicitly override the original public host to loopback without editing original files. Launcher `--open` opens a browser. The initial wrapper resolved the virtual-environment interpreter symlink to system Python; preserving the intended existing environment fixed startup without installing packages. Original hashes and failed startup evidence remain. Unrelated existing listeners were preserved.

## Live retrieval and context

| Worker / allocation | Actual prompt / output tokens | Result | End-to-end latency |
| --- | --- | --- | --- |
| P6000 / 8,192 | 7,697 / 81 twice, uncached | LIVE_PASS, all three exact values twice | 36.578 s, 37.609 s |
| P40 / 8,192 | 7,697 / 81 twice, uncached | LIVE_PASS, all three exact values twice | 39.282 s, 39.703 s |
| P40 / 16,384 | 15,371 / 75 twice, uncached | LIVE_PASS, all three exact values twice | 80.453 s, 111.968 s |
| P6000 / 16,384 | 15,371 / 75 twice, uncached | LIVE_PASS in cycle two, all three exact values twice; first cycle BLOCKED before inference | 74.984 s, 76.828 s |
| P6000 / 32,768 | 30,794 / 78 twice, uncached | LIVE_PASS, all three exact values twice | 174.766 s, 175.953 s |
| P40 / 32,768 | 30,794 / 78 twice, uncached | LIVE_PASS, all three exact values twice | 229.078 s, 286.953 s |
| P6000 / 65,536 | 61,587 tokenized input; no received output | FAIL on first request, no retry or promotion | ReadTimeout at 300.015 s |
| P40 / 65,536 | 61,587 tokenized input; no received output | FAIL on first request, no retry or promotion | ReadTimeout at 300.000 s |
| Strata / 8,192 | Full 7,697 / 81 twice | LIVE_PASS after documented accounting correction, all three exact values twice | 16.859 s uncached; 3.110 s with 7,690 cached input tokens |

At 8K, actual server prefill was 245.59–252.79 tokens/s on P6000 and 234.17–237.27 on P40; completion was 12.90–13.07 and 11.72–11.75 respectively. P40 16K measured 150.83–212.98 prefill and 7.38–8.96 completion tokens/s. These are observed prompts/runtime measurements, not guaranteed throughput. Near-limit non-streaming probes did not measure time to first token; near-limit TTFT remains unknown.

Separate prospectively sealed short streaming probes subsequently measured actual client time to first nonempty answer content: **906 ms P6000, 1,547 ms P40, 2,093 ms Strata**. End-to-end times were 2,297, 3,063 and 3,031 ms. Each actual request used 72 prompt and 23 completion tokens, zero reported cached tokens, returned the exact sealed ledger and completed with stop/DONE. These are warm loaded workers and short prompts, not cold startup or near-limit TTFT. Role-only/empty/reasoning/keepalive events are excluded. No structured-format validator was requested because existing Strata can buffer validated structured output before streaming. The streaming oracle SHA-256 is `d42288e0d3be4f5b5dff1fe811d07aa5c807c164bf5cfb673c01bcb7c75378b5`; no retuning or retries occurred.

The original Strata artifact says FAIL because the verifier counted only seven fresh input tokens on repetition two. Independent direct inspection of unchanged server source proved full context splits into `input_tokens` plus `cache_read_input_tokens`. The unchanged actual token-count endpoint returned 7,697. Both model answers exactly retrieved all three prospective values with `end_turn`. A separate accounting erratum sums 7 + 7,690, preserves original FAIL bytes/hash, and persists a genuine 8,192 proof without rerunning inference or changing answers. The second latency is a cached repetition, not uncached prefill throughput.

Both GPU workers passed sequential 8K, 16K and 32K stages under the same f16 KV profile. The 32K probes ran concurrently on distinct GPUs sharing Athena CPU/memory resources; their timing scope reflects that concurrency. Actual independent 32K process/device inspection measured P6000 used 18,762 MiB / free 5,675 MiB and P40 used 18,758 MiB / free 5,681 MiB, with both assigned process contexts 32,768 and loopback listeners. These measurements prove allocation and resource use, while the separate actual retrieval responses prove near-limit behavior.

Both actual 64K first requests failed at the protected 300-second request budget. Each prompt was actually tokenized to 61,587 tokens; neither received an inference response. No second request, retry, capacity promotion or higher-stage inference followed. The failure establishes the campaign budget boundary, not a physical context hard limit or an OOM diagnosis; eventual completion and output quality are unknown. Largest accepted GPU context remains **32,768**. Independent inspection during 64K allocation measured P6000 used 22,400 MiB / free 2,037 MiB and P40 used 22,394 MiB / free 2,045 MiB, with exact owned process/device associations. Successful allocation alone does not verify retrieval.

The current all-GPU Q4_K_S/f16 128K profile is **UNSAFE_TO_RUN** by independently audited memory preflight; no 128K launch or inference occurred. Actual GGUF tensor headers establish sixteen main full-attention layers, four KV heads and 256-wide key/value vectors. This gives 65,536 KV bytes per token and 6,144 MiB additional KV memory from 32K to 128K. Adding that to independently measured 32K used memory produces lower bounds of **24,906 MiB P6000 / 24,902 MiB P40**, already exceeding each physical 24,576 MiB before any additional compute-buffer growth. These are calculated lower bounds, not measured 128K allocations. Different weight/cache/offload profiles remain separately unverified.

Model metadata 262,144 and original Strata configured 131,072 were never represented as successful runtime tests. No stage was raised after an actual inference failure. The initial P6000 16K disconnect was independently isolated to the dead Windows relay while its exact owned remote server remained healthy; logs contained no OOM. Original discarded relay stderr means its underlying cause remains unknown.

## Actual original workflows

Independent read-only reconciliation compared four retained real GPU responses against the original workflow SQLite database. Both campaigns contain the original file-read and two analysis steps, all verified by the original controller. Jobs match authoritative workflow, step, invocation, output digest and cited-observation report. All actual model reports correctly compute the unchanged synthetic 9/10 percentage as 90.

Sequential execution took 18.078 seconds on one GPU. Parallel execution took 12.766 seconds on two distinct GPUs, with 8.486 seconds of actual overlap: observed 29.38% duration reduction / 1.416 ratio. Planner fixture is explicitly disclosed; analysis inference, original permissions/file reading/report verification/persistence are real. KV reuse differs across requests (cached tokens 0, 0, 624, 416), so this workload does not prove universal scaling, uncached performance or broad intelligence.

The final three-worker campaign separately passed independent read-only reconciliation: **39.407 seconds sequential / 10.203 seconds parallel**, each with four original verified steps and three verified analysis jobs spanning P6000, P40 and original Strata. All six actual reports return the same correct 90 with unchanged citations. All-three execution overlap is 8.442 seconds. Each campaign emits 330 completion tokens, giving observed aggregate 8.374 / 32.343 completion tokens per campaign second. The 3.862 ratio / 74.11% duration reduction is confounded by GPU cache reuse (zero sequential, 416 tokens on each parallel GPU) and warm runtime effects; Strata reports zero cache reuse in both. It is not a cache-controlled threefold scaling claim. Fixture planning remains explicitly disclosed and does not hide the fresh-primary-model boundary below.

Earlier failures remain: the original 30-second step budget paused campaign one; campaign two's queued request expired when its campaign omitted the health monitor. Passing campaign three uses the original monitor and an explicit bounded budget. These failures were not erased.

A separate fresh-goal test used the unchanged actual 4B primary model and original controller, with no supplied plan. Independent inspection confirms **PARTIAL / BLOCKED** after 19.219 seconds: model outline criteria invent undeclared result paths, its binder incorrectly treats supported deterministic analysis/source reads as unsupported, and its artifact binding supplies literal prose rather than a verified predecessor reference. Original bounded-plan validation rejected the output and installed zero steps, invocations, compute jobs or artifacts. Passing distributed calculations with a disclosed planner fixture therefore do not establish autonomous complex-goal planning; the primary model was not replaced to conceal this boundary.

## Independent implementation checks

Controlled tests use actual registry, HTTP transport, scheduler, original WorkflowService, permissions, file-read handler and evidence verification. Inference endpoints are explicitly controlled loopback HTTP servers with a disclosed planner fixture; their tests establish implementation behavior, not GPU performance.

Checked invariants include removed authorization, null telemetry, model mismatch, redirect rejection, strict SSH forwarding, pre-dispatch cancellation, durable uncertainty without replay, prompt/output receipt rejection, actual simultaneous HTTP reservations, exact associations, measured-context admission, category gates, late-result rejection, occupied/uncertain startup refusal, changed-model proof invalidation, original parallel workflow steps and rejection of wrong or malformed remote reports.

Independent findings prompted repairs for transitive memory/screen provenance, canonical Google Gmail/Docs/Drive capabilities, imported MCP/external definitions and conversation derived from owner goal descriptions. Authorized remote fixtures explicitly permit project plus conversation; a separate project-only case proves the description never crosses HTTP. Five original classifier failures remain in their XML; the repaired 36-case cycle passed. A later actual-HTTP reassignment case passed and retained the first worker's interruption/attempt history and durable result.

Two late regressions reproduced auxiliary defects in controlled temporary directories: a second read-only registry changed an open owner's RUNNING job to LOST_CONNECTION; a Windows directory junction permitted reading/mutating a foreign compute database. Original two-failure XML is retained. The unchanged independent regressions now pass: reads do not infer controller death, the original current workflow owner alone reconciles recovery, and escaped receipt/context-proof storage is rejected. Explicit dispatcher close reports its own unverified job uncertainty.

A further controlled proof-binding audit reproduced stale capacity after either KV cache type changed. Both unchanged independent regressions now pass: runtime fingerprints include key/value cache types, invalidating current and prior-stage proof on changes. Actual campaign f16 settings and raw retrieval results did not change; genuine matching evidence is explicitly reimported under the repaired identity. The final 41-case independent cycle passed with zero skips or errors. Four separately rerun cached-Anthropic helper cases passed with controlled mocked transport; the actual live Strata evidence remains separately labeled.

Independent parsing of the root's final full-regression XML confirms **1,728 passed, two skipped, zero failures or errors**, 1,730 total in 249.924 seconds. XML SHA-256 is `103682f6c7959d49e30416a9bf8e0c3ce1b23fe0239ea3843612f8e8715225b8`. The verifier parsed this root-owned run rather than repeating it. An earlier transient MCP fixture startup failure remains preserved; unchanged fixture/security tests and the final full run subsequently passed.

Logging hygiene is **PARTIAL**: during engineering cleanup, an overly broad JSON-line search echoed an existing Strata API credential from an ignored protected raw configuration artifact into a tool response. The incident was disclosed without repeating the credential. It was not added to a committed source file or a new artifact. Subsequent checks use parsed metadata and hashes only. Original user authentication/configuration was preserved; no credential rotation was silently performed. Functional privacy/network/permission regression passes do not erase this actual transcript-logging incident.

## Native screenshot review

Actual portable native HANNI windows were physically captured from foreground Win32 HWNDs. Screens were checked at 1920×1080, 1440×900, 1366×768 and 900×650 with actual telemetry and saved workflow history. Reviewer inspected ordinary/compact screenshots plus real worker diagnostics, node details and completed distributed assignments.

| Screen | Hierarchy / 2 | Typography / 2 | Density / 2 | Consistency / 2 | Controls / 2 | Total / 10 | Template feel / 10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cluster | 1.8 | 1.8 | 1.7 | 1.8 | 1.7 | **8.8** | **1.0** |
| Models | 1.8 | 1.8 | 1.6 | 1.8 | 1.7 | **8.7** | **1.0** |
| Workflows | 1.8 | 1.8 | 1.7 | 1.8 | 1.7 | **8.8** | **1.0** |

Subjective scores exceed 8.5. Cluster retains horizontal readable rows, truthful missing/connection states and repair jellyfish. Models separates configured, server-reported and empirically verified context with explicit unknown queue/throughput. Workflows retains successful and blocked saved outcomes and actual assignments, delay, verification and selection reasons. Long real model/goal paths modestly reduce density but remain readable and scrollable.

Latest sequential native campaign passed nine checks: protected enable configuration changed/restored, limits displayed, actual HANNI node included registered workers, saved assignments appeared, selection reasoning expanded, and no JavaScript errors/model-start requests occurred. Power, terminal, microphone, chat submission and server-start actions were not clicked.

After all repairs and genuine runtime-proof imports, the final matched three-worker preview passed **eleven** native checks with six physical frames: the actual Strata worker and its 8K diagnostics are inspectable, both GPU rows show actual verified/configured/reported 32K, and all three saved assignments remain visible by natural scrolling. The reviewer inspected the final pixels and retained the same 8.7–8.8 component grades. Safe enable configuration was restored and no JavaScript errors or startup requests occurred.

The larger existing native framework passed 41 relevant checks and produced sixteen physical frames. Its sole raw failure expects an enabled chat composer, but this isolated preview intentionally has no local chat controller; disabling it is correct. Live chat is outside this review. Earlier harness failures from cold CDP discovery, a missing asynchronous wait and competing foreground capture remain recorded. The latest sequential campaign fixes those harness issues; the window guard rejected an occluded capture rather than providing misleading pixels.

## Reproduction and evidence

Raw private evidence is ignored under `data/v37-verification`. Native captures are bounded to the owned HANNI window. No private addresses, authentication values or user memory/conversation/screen contents appear in public review source. Protected deployment and credentials remain outside committed source.

Final independent read-only cleanup confirms both 64K and prior 32K owned Athena PIDs are absent, both owned loopback ports refuse connections, and NVIDIA reports no compute processes. On Wonyoung the owned Strata cohort PID is absent and its owned port is closed; the unrelated original Python PID/listener remains, and original launcher, configuration and server-source hashes match the independent baseline. Root closed its local preview, relays and controller. Cleanup performed no new inference and did not alter original user services.

- `sealed/protocol.json` and digest: prospective oracle.
- `hardware`: strict-key observations, original metadata/source hashes, actual Strata cache semantics.
- `context`: real responses/timings, blocked preparation, original Strata FAIL and accounting erratum.
- `context/p6000-64k-cycle1.json`, `context/p40-64k-cycle1.json`: actual first-request budget failures, with no output or accepted capacity.
- `128k-preflight-independent-audit.json`: independently calculated current-profile memory lower bounds, without a 128K launch.
- `hardware/athena-final-cleanup-independent.json`, `hardware/strata-final-cleanup-independent.json`: independent read-only process, port, GPU and original-file preservation checks.
- `independent-canonical-privacy-cycle1.xml`: five preserved failures; `independent-privacy-repair-cycle2.xml`: passing repair.
- `auxiliary-storage-recovery-cycle1.xml`: both preserved late failures.
- `workflow-benchmark-independent-audit.json`: actual reports reconciled with original read-only DB.
- `fresh-primary-planner-independent-audit.json`: actual unchanged primary-model planning boundary, with original output/result hashes.
- `workflow-benchmark-three-worker-independent-audit.json`: six real responses reconciled with original four-step workflows and actual all-three overlap.
- `streaming-ttft-cycle1.json` and sealed streaming protocol: actual content deltas, client timing and zero reported cache reuse.
- `independent-final-cycle4.xml`: 41 independent cases pass; earlier failure XML remains preserved.
- `root-full-regression-independent-parse.json`: independent parsing and digest of root's 1,728-pass/two-skip final full run.
- `native-final`, `native-controls-final-cycle2`, `native-visual-score-final.json`: physical pixels, safe controls, subjective components and hashes.
- `native-three-worker-final-cycle2`: final matched repaired source, eleven passing controls/checks and actual three-worker physical frames.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\integration\test_compute_v37_verifier.py
```

Hardware probes use protected deployment and bounded read-only strict SSH. Context scripts require assigned exclusive owned endpoints and prior same-worker passing stages. Accounting correction performs no inference; benchmark audit opens the original DB read-only and performs no model call. Root owns final full regression, checkpoints, owned runtime cleanup and commits.

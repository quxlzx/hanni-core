# Original-source configured-model baseline

The verifier ran all **60 sequestered final cases** against original commit `791bdab9e4921e2958c20b55fdfadb7ce44e04d6`, using genuine cached **Qwen3.5-4B-Q4_K_M** inference through the original client, CLI binding, MCP host/session and registry permission/schema/audit boundaries. No deterministic model replaced inference.

An ephemeral loopback endpoint and persistent verifier-private isolated data were used. The cached GGUF was passed explicitly; no download occurred. Original settings remained context 16384, max tokens 768, temperature 0.35, top-p 0.9, single parallel slot and configured quantized KV. Native runtime reported **Vulkan1, 33/33 layers offloaded**. Owned PID 41276 was shut down; external model PID sets were empty before and after. Startup and one neutral warmup were excluded from task timings. The source snapshot imports the original package before the editable current repository.

| Measurement | Original baseline | Sample / Wilson 95% interval |
|---|---|---|
| Required candidate-menu sufficiency | 63.64% | 28/44; 48.87–76.22% |
| Correct tool selection, all tool requests | 63.64% | 28/44; 48.87–76.22% |
| Actual model selection when menu sufficient | 100% | 28/28; 87.94–100% |
| Correct no-tool execution decisions | 81.25% | 13/16; 56.99–93.41% |
| Controlled selection plus lexical evidence-answer completion | 68.33% | 41/60; 55.77–78.69% |
| Structural model arguments | 100% | 50/50 raw calls against original built-in plus pinned dynamic schemas |
| Historical semantic argument claim (superseded below) | Previously reported100% |48/48 adapter flags; not48 independent semantic assertions |
| Unknown tool wire names | 0 | 50 raw model calls |
| Forbidden write-adapter entries | 0 | 60 requests; not a guarantee for all possible requests |
| P50 task latency | 1280.39 ms | 60 tasks, one warmed inference pass |
| P95 task latency | 2666.75 ms | Nearest-rank percentile over 60 tasks |

Fifty raw calls and forty-eight controlled adapter executions differ because the original controller suppresses repeated successful calls. This difference does not constitute invalid arguments. No-call cases are not counted as argument successes. Twenty-eight sufficient tool-request menus all used actual model tool selection; seventeen total cases bypassed the tool-capable model loop through blocked/fallback/original deterministic paths, so the conditional model statistic uses only the twenty-eight relevant cases.

**Evidence limitations:** handlers return immutable synthetic read-only fixtures behind the genuine registry. This is original-controller/model evidence, not a claim that all production handlers or external providers work. The single synthetic dynamic metadata capability measures discovery/withdrawal and model integration without a production MCP service; existing separate genuine SDK tests cover wire transport.

Final-answer checks are conservative lexical support checks, not a semantic judge. Calendar fixtures return synthetic event evidence without independent provider retrieval or full requested-window outcome validation. Structural schema validation cannot prove every argument satisfies the user's intent. Therefore the 41/60 controlled metric is **not advertised as independently verified task completion**, real calendar success or measured current-machine diagnostics. Stronger production outcome claims remain unmeasured until the controlled workflow and real-read evidence are available. Live-model results must not be combined with deterministic workflow clients without disclosure.

The 60-case query/expected-tool corpus remains private with SHA-256 `b1ccb0aa512a95f418582d7bc7814f096af6788be7da7f13e3bbd686ae433d25`. The live fixture/oracle was pinned before first inference with SHA-256 `378f369023c0af6f289123fdbdbb3189b5ac43b66e4f774bae4c6306f81b61e2`. No query, individual failure or expected answer was disclosed for tuning; expected retrieval answers remained unchanged after baseline. Offline structural argument auditing used the original schemas and pinned dynamic definition, not new production answers.

Final-source evaluation must run only after source freeze, once against this untouched corpus, with identical original configuration, fixture/oracles and model/hardware. Record quiet-host load and compare paired case outcomes with exact sample counts. If final results are disclosed, this corpus is future-contaminated and must never be reused as independent unseen development evidence.

## Post-evaluation audit correction and publication

The earlier48/48 semantic-argument statement overstated independent coverage: the adapter explicitly validates expected search terms only for `file.search`; other adapters assign a default true flag. The authoritative baseline semantic result is **2/2 independently checked file-search calls**, Wilson95%34.24–100%, while **50/50 structural model calls** and **48 actual adapter entries** remain correct separate counts. No-call cases or unexamined semantic fields are not counted as argument successes. The unchanged final run also has2/2 independently checked search calls. This clarification changes reporting, not any evaluator or expected answer.

The original published `b1ccb0aa512a95f418582d7bc7814f096af6788be7da7f13e3bbd686ae433d25` hash is the generated LF-normalized case text. Unchanged Windows CRLF raw bytes hash to `84e492db6d9dcaa66023c100af6637f1b67dc47ecbd585384993b19d541784b9`. All sixty case fields match the original baseline artifact; no input drift occurred. These exact immutable inputs/evaluators are now published only after the once-only final evaluation at `evals/reliability/v2_final_holdout/`; future development must use a fresh sequestered holdout. See [final independent conclusions](m5-final-evaluation.md).


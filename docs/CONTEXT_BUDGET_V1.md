# Qwen context budget audit

The [measurement artifact](../evals/llm_tools/results/context_budget_v1.json) uses saved Qwen3.5-4B tool-eval transcripts. Model-server `prompt_tokens` counts are cumulative across tool rounds; they are **not** peak context-window measurements. Character counts below are exact serialized payload lengths, not separate token counts.

| Case | Prompt tokens (cumulative) | Tool calls | Tool schema characters | Mock-result characters |
| --- | ---: | ---: | ---: | ---: |
| No-tool conversation | 338 | 0 | 0 | 0 |
| Direct system question | 1,647 | 1 | 1,026 | 105 |
| CPU diagnosis | 3,582 | 3 | 2,006 | 996 |
| Calendar read | 1,606 | 1 | 526 | 445 |
| Mixed Calendar/system | 2,861 | 2 | 862 | 572 |

The shared tool policy is 1,479 characters in these cases. Tool schemas and repeated tool-round context dominate beyond that. The current small routed menus matter more than shortening the owner's request. The benchmark has no multi-turn dialogue history, so it cannot establish a history budget; production's existing 20-message/120-second bound remains the safety net.

Keep one concise tool policy, the existing small routed menu, and bounded tool results. Do not drop safety or evidence rules for a cosmetic token saving. Before increasing tool-round or history limits, measure peak prompt tokens from the model server and run a multi-turn LLM corpus; cumulative usage alone cannot prove headroom against the configured context window.

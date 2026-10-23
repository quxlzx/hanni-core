# HANNI Routing Eval v1 — Untuned Baseline

Baseline captured after the Google-Calendar-only / natural-language-routing checkpoint,
before tuning the router against this 750-case corpus.

**Important:** these scores measure capability retrieval and deterministic argument
resolution only. They do not execute tools and they do not yet measure the resident
model's final function choice after retrieval.

| Family | Cases | Avg. score | Strict pass |
|---|---:|---:|---:|
| Diagnostics | 250 | 78.45 | 19.20% |
| Google Calendar read | 90 | 80.10 | 67.78% |
| Google Calendar create | 70 | 97.54 | 80.00% |
| Files | 60 | 84.59 | 46.67% |
| Process/system | 55 | 73.75 | 7.27% |
| HANNI/model/Google/Gmail | 40 | 76.68 | 30.00% |
| Date/time/utilities | 40 | 88.43 | 57.50% |
| Ambiguous/fallback | 40 | 54.88 | 5.00% |
| Unsupported write safety | 40 | 92.50 | 90.00% |
| Mixed-domain | 35 | 72.50 | 14.29% |
| Slang/typos | 30 | 62.78 | 13.33% |
| **Overall** | **750** | **79.60 / 100** | **37.20%** |

## What the baseline already tells us

1. **Calendar creation is the strongest current route.** Most failures are event-title
   cleanup (`"dinner on"` / `"dinner for"`) rather than choosing the wrong domain.
2. **Calendar reads are useful but too grammar-sensitive.** Phrases such as “what am I
   doing tomorrow?” frequently miss the deterministic calendar resolver.
3. **Broad diagnostics retrieve the main capability but expose too much noise.** For
   “why is my PC slow?” `system.performance` is often correctly first, but irrelevant
   tools consume the five-tool budget instead of CPU/RAM/GPU/disk diagnostic companions.
4. **Vague language over-routes.** Generic conversation such as “what do you think?”
   frequently receives unrelated tools instead of falling back to normal conversation.
5. **Write blocking needs more verb coverage.** `kill`, `delete`, and many mutations are
   blocked correctly, but synonyms such as `terminate`, `erase`, `minimize`, and `run`
   reveal read tools in a few cases. No capability is executed by this benchmark.
6. **Mixed-domain routing is immature.** The retriever usually captures only one half or
   fills the remaining tool budget with lexical noise.
7. **Slang/typo robustness is currently weak**, which is particularly relevant for voice
   transcription and short casual owner requests.

This file is a historical baseline, not a target. Future routing work should improve the
scores without weakening case expectations just to make the number go up.

Corpus SHA-256: `b42032834d9b184f352b67103bdb11a1cbc51e27f42e99fc9928313c6acd80bc`

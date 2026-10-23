# Routing benchmark baseline (September 23, 2026)

The current deterministic router scores **99.82% strict pass** and **99.66/100 average** across **1,087 cases** using the live **150-capability** registry. The 150-case LLM benchmark is separate: it tests what Qwen does after routing. These are development-corpus measurements, not a held-out accuracy estimate.

| Scope | Cases | Strict pass |
| --- | ---: | ---: |
| Original natural-language families | 750 | 100.00% |
| Registry and hardening probes | 337 | 99.41% |
| All cases | 1,087 | 99.82% |

The original 750-case comparable baseline was **49.33%** before routing hardening. Its raw first run was 47.6%; the comparable score corrects a GPU-process domain-mapping inconsistency without changing captured selections. The current 100% on those same cases is a development-regression result and should not be treated as unseen-language accuracy.

The only two current strict failures are `REGISTRY-spotify.play_pause-1` ("Can you play Spotify?") and `REGISTRY-spotify.play_pause-2` ("Pause my Spotify music"). Both retrieve `spotify.play_pause`, plus `spotify.status` and `spotify.launch`; the strict probe flags the latter two as irrelevant exposure. They are plausible supporting capabilities for playback state, so the router is being left as-is rather than adding brittle phrase exceptions. No capability is missing or unreachable in the coverage audit.

Machine-readable artifacts are [`after.json`](after.json) and [`capability-coverage.json`](capability-coverage.json). The earlier `before.json`, `before-comparable.json`, `comparison.json`, and `before-expanded.json` remain historical reference runs; their prompts, scoring, or probe annotations are not all identical to the current full run. Routing is considered stable pending a real regression.

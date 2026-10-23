# Language V3 development probe

[Language V3](../evals/routing/language_generalization_v3.jsonl) contains 150 fresh, owner-style development requests: 40 diagnostics, 30 mixed-domain, 20 app/media, 20 Calendar/time, and 10 each for HANNI/model, files, safety, and no-tool conversation. Its SHA-256 is `d897ddf65f0429dc5c0980b2acdfa3d774d92c9ba322128e0f98da82c52c5750`. It is development data, never a blind holdout. Historical V2 fixture dates and timezone were not changed; V3 uses a pinned New York date.

The [routing result](../evals/routing/results/overnight_language_v3.json) is **63.33% strict** with 65.45% required-tool recall, 50% mixed-domain family recall and 10% no-tool false positives. Companion tools were annotated only when they could plausibly help the requested task; this corrected an initially overstrict precision oracle. The remaining failures include concrete misses on quiet/indirect symptoms such as a laptop becoming slow off the charger and file-loading disk activity. The frozen router has not been altered to fit these phrases.

The [600-variant development mutation run](../evals/routing/results/language_v3_mutations.json) scored 61.83% strict versus 63.33% clean, with zero blocked-action tool regressions. Its simple article/spacing ASR-like class scored 57.33%; it is **not** a Whisper fidelity test. The [200 final-turn mutations](../evals/routing/results/multiturn_mutations.json) scored 86.5% dialogue success versus 100% clean. These are useful failure probes, not evidence of unseen-language reliability.

The roadmap's ≥90% Language V3 development gate is unmet. Keep blind Holdout V2 uncreated and sealed until the generalization and safety results justify a freeze.

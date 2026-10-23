# Routing generalization lessons

The old 1,087-case routing suite and Language V2/V3 were development and
regression data. Near-perfect scores showed that known wording remained
supported. They did not establish performance on unseen owner language.

The sealed Holdout V2 run exposed the gap: only 48 of 72 menus were sufficient
(66.67%), although Qwen completed 45 of those 48 tasks (93.75%). This points
primarily to retrieval, not a reason to change the Qwen prompt. Exact Holdout
V2 prompts and expected outcomes remain untouched and are not used as new
development examples.

V4 uses 300 new development cases. Compared with V2 and V3, 39.25% of its
unique tokens, 77.62% of unique bigrams and 93.08% of unique trigrams are new.
Those lexical measures check for obvious duplication but do not prove semantic
novelty. V4 reached 97.33% strict success and 97.71% required-tool recall after
development.

A separately written, hash-locked 100-case V4B set scored **80% on its untouched
first run**, below the 85% development gate. Structural follow-up raised it to
94%, but that later score is development tuning, not a replacement first-run
result. Another genuinely fresh check is needed before a new blind holdout.

The main lessons are:

- Keep benchmark roles separate: regression, new development, untouched
  development check, and blind holdout are different levels of evidence.
- A larger synonym table can saturate known data while leaving new meanings
  unresolved. Missing anchors should lower lexical confidence rather than
  suppress candidate scoring entirely.
- Broader recall must be paired with no-tool and safety audits. A separate
  20-case educational/conversation audit caught false live-tool exposure.
- Mixed requests need conservative clause splitting and menu reservation so
  one domain does not consume every slot.
- Preserve locked hashes and first-run reports even when later development
  improves the same corpus.

Holdout V3 was not created, and Tool Intelligence V1 is not frozen.

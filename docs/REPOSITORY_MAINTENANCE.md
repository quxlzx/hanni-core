# Repository maintenance

`src/`, `frontend/`, `desktop/`, `scripts/`, and `config/` contain supported code,
build sources, launchers, and configuration. The native chat and Windows voice
paths share components; a module without a native-chat import can still be used
by the voice assistant or desktop dashboard.

`tests/`, evaluation inputs and freeze manifests under `evals/`, and the final
reports under `docs/` support regression checks and explain their limits.
Keep them with the source. The assistant harness run guide is
[here](assistant-harness/testing.md).

The October 24 cleanup removes superseded intermediate Campaign 8 static
scorecards, unused debug scripts, a broken duplicate source-export launcher, a
launcher misplaced in the wheel cache, and inactive archived skill copies.
The final historical UI ledger remains at
[static-controls-final-cycle3](campaign8/static-controls-final-cycle3/STATIC_SCORECARD.md).
All 24 active skills remain under `soul/skills/`. Earlier intermediate reports
and retired skill files can be inspected at commit `a57f585`, for example:

```powershell
git show a57f585:docs/campaign8/static-controls-cycle1/STATIC_SCORECARD.md
git show a57f585:soul/archived-skills/README.md
```

Root `START_BRAIN.cmd`, `START_HANNI.cmd`, `START_HANNI_OS.cmd`, and
`EXPORT_HANNI_SOURCE.cmd` remain available. Voice asset setup uses the existing
`scripts/setup_hanni_voice.py`; see [voice setup](SIGNATURE_VOICE.md).

Build output, Python caches, `.pytest_cache/`, package metadata, source archives,
and optional offline wheel caches are generated files. Git ignores them. The
main `.venv/` is the installed application environment; keep it while running
HANNI. Test run logs and coverage under `.pytest-work/assistant-harness/` remain
local evidence referenced by the committed verification report.

`data/` and `state/` contain local records, configuration, conversations and jobs.
`models/` and `binaries/` contain downloaded runtimes and weights. They are not
part of source cleanup. Remove their contents only as an explicit data reset or
runtime uninstall, with the relevant application stopped.

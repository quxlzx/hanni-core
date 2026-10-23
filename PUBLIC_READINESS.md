# HANNI publication readiness ? experimental alpha

**Ready to publish this sanitized source copy as an experimental alpha. A stable release is not certified. Do not publish the original working repository or its Git history.**

The complete final Windows run recorded **4,644 passed, zero failures/errors, and 6 skips** (pytest/JUnit includes controlled subtests). All **45 frontend tests** passed. The final app/test source remained unchanged during validation. Clean Python/npm installation, frontend compilation, CLI health, wheel/source builds, source privacy and distribution privacy checks passed. npm reported zero advisories. The built wheel installed and ran core imports/CLI health in a second clean environment; all 216 Python modules matched reviewed source. The console entry-point test was separately rerun with the virtual environment on the child process PATH and passed.

## Changes

- Removed deployment addresses, owner home paths and candidate credential strings from the public copy; retained original private configuration and history.
- Preserved network and sender categories in synthetic fixtures so anonymization does not invalidate safety tests.
- Included missing JavaScript helpers, licensed font assets and complete Python source in exports/packages.
- Added clean development dependencies, CI privacy/history auditing, frontend tests and the correct Windows virtual-environment layout.
- Updated workflow read instrumentation to observe actual raw-byte reads; retained raw-digest verification and execution protections.
- Versioned schema-only coverage metadata without changing historical behavioral oracles or acceptance scores.
- Made Hermes inventory depend on matching enabled private roster/tunnel references; removed fixed deployment addresses from setup code. No remote service was modified.
- Corrected the voice display to distinguish synthesis preparation from active playback; retained internal speech exclusion, interruption and notification guards.

## Reproduce from the extracted source

Install Python 3.12, Node 24 and Git. Open PowerShell in the extracted `hanni` folder. Initialize an empty local repository so privacy checks use the included ignore rules; no remote or commit is created:

```powershell
git init
python scripts/validate_public_release.py --candidate . --reports ../hanni-validation-private
python scripts/audit_public_release.py --history --report ../hanni-validation-private/history.json
```

The validator installs software dependencies, runs the frontend/full Python checks, checks CLI health and builds/audits packages. It downloads no models or browsers and does not publish. Keep detailed logs private outside the public copy. Optional missing integrations remain marked NOT TESTED. The release metadata files are excluded from the validation source digest because this verdict is written afterward; the final archive digest binds the packaged files.

For normal application setup, follow README's Windows instructions. Models and account credentials are not included. Configure private node/endpoint references and approvals locally; never copy live `data/`, `.env`, token files, older archives or the original `.git` into this copy. Preserve the original project for rollback; do not replace its live settings with anonymized examples.

## Remaining acceptance gates

Physical microphone/TTS responsiveness, live model held-out task quality, external account integrations, remote deployment and the separate Control Center deployment are **NOT TESTED** for this release. The optional LangGraph/Torch adapters and privileged Windows symlink case were unavailable in the core test environment. P50/P95 text/planning latency and first audible useful-answer latency are **NOT TESTED**, not inferred from test duration or token throughput. Historical correctness/residency failures remain evidence; no higher assistant-quality grade is claimed. Unattended intent execution remains disabled until its individual task-family gate passes.

The six full-run skips and all gate results are listed in `PUBLIC_READINESS.json`. Earlier failed runs remain in private evidence. GitHub-hosted CI itself has not run because nothing was pushed. Publish as a preview with these limitations visible; run the missing acceptance scenarios before describing HANNI as stable.

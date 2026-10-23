# Public release preparation - 2026-10-13

The private working repository is **not ready to make public**. The source tree and reachable Git history contain deployment addresses and owner paths. Removing current values alone does not remove historical blobs. A local pre-push privacy audit is installed without replacing an existing hook; source exports now refuse detected exposures. Local ZIPs, build archives and backup files are ignored. No history was rewritten and nothing was pushed.

A separate history-free candidate was prepared outside this repository. Its source scan found no remaining addresses outside loopback/documentation ranges or flagged credential strings. This is a pattern-based audit, not proof that every possible secret format or personal detail is absent. Known private bridge-token/environment values were compared in memory against source and history with no matches. Recognizable API-key matches in the preliminary scan were task-name false positives; generic assignments in test fixtures were anonymized.

The initial public-copy unit baseline produced 1,789 passes, 21 failures and two skips out of 1,812 tests. Its failures remain in private evidence. Repairs preserve valid and invalid fixture distinctions, include omitted JavaScript helpers and licensed fonts, provide clean test dependencies, and update read instrumentation to the actual raw-byte implementation. The optional separate Control Center source and Torch adapter are explicitly NOT TESTED when absent. Current results belong in the release copy's `PUBLIC_READINESS.json`; old results never substitute for final validation.

Anonymization changes historical fixtures and report digests. Original evidence is retained privately, and old scores must not be represented as newly validated public results. Schema-only coverage metadata has a separate versioned migration; historical inputs, behavioral expectations and acceptance scores are preserved. A successful software gate permits an experimental source preview only. Physical voice, current-model held-out quality, owner accounts, remote deployment and the separate Control Center integration require their own acceptance evidence before a stable release.

Reproduce audits without printing matched values:

```powershell
python scripts/audit_public_release.py --history --report data/public-release/audit.json
python scripts/prepare_public_release.py --output C:/Projects/HANNI_PUBLIC_NEW_CANDIDATE
python scripts/validate_public_release.py --candidate C:/Projects/HANNI_PUBLIC_NEW_CANDIDATE --reports C:/Projects/HANNI_PUBLIC_VALIDATION_PRIVATE
python -m pytest tests/unit/test_public_release_audit.py tests/unit/test_release_ignore.py tests/unit/test_distribution_safety.py -q
```

Do not copy private `data/`, `.env`, backups, old ZIPs or the original `.git` into a public repository. Credentials belong in environment references or the existing owner-controlled stores; node details and approvals belong in ignored runtime configuration. The public candidate uses an independent empty Git repository with no remotes or commits.

Validation creates an isolated `.venv`, installs software dependencies, installs and builds the frontend, runs its tests and the full Python suite, checks CLI health, builds distributions and audits privacy. It downloads no models, opens no microphone, starts no production inference service and does not publish. Test seams remain controlled evidence. Logs stay outside the public source; the report verifies source did not change during testing. CI uses the same virtual-environment layout and tests the frontend before checking that committed assets reproduce exactly.

To roll back these release preparations, use the retained private working project. Delete only the independently prepared public copy if desired; do not restore its anonymized configuration over live private settings. No model defaults, remote services or original Git history were changed by publication preparation.

If a real key is discovered in previously shared history, revoke or rotate it before history cleanup. GitHub documents this process at https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository. A destructive rewrite or force push requires a separately reviewed action.

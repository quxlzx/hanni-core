# Cluster reboot fix

2026-10-09. Reboot now uses `/usr/bin/systemctl -i reboot`. The previous command
explicitly respected inhibitors and required noninteractive authorization. The
owner requested sudo with an inhibitor override and supplied a password.

Non-root execution uses `sudo -S -p '' -- /usr/bin/systemctl -i reboot` when a
saved credential is available. The password is sent only over SSH stdin, never
in command arguments, frontend responses, source or operation history. Existing
passwordless sudo uses `sudo -n -- /usr/bin/systemctl -i reboot`; an existing
authorized Tailscale root connection executes the same systemctl command directly.
The root capability check verifies the installed binary and does not require an
inhibitor policy decision that the requested `-i` explicitly overrides.

The confirmation describes the shutdown-blocker override. Fixed node/action
allowlists, UUID deduplication, reservation locking, fresh SSH samples, capability
expiry, explicit confirmation, same-origin/token checks, Safe Mode and maintenance
exclusion remain enforced. Sleep keeps its existing command and inhibitor policy.
Unknown disconnect/timeouts are not automatically retried. A known Tailscale
preauthentication failure is reported as failed with a sign-in explanation;
ordinary unacknowledged SSH disconnection remains unknown.

## Credential setup

The owner-supplied password was saved for the eight active roster nodes in
**Windows Credential Manager**, using the existing installed keyring dependency
with its explicit WinVault backend. No plaintext fallback is allowed. Keys are
scoped to the resolved HANNI data directory and each fixed node/account/address;
isolated test sessions do not read production credentials. Values use HANNI's
Secret wrapper and in-memory log redaction. Yunjin receives no credential/probe.

To replace one node's password, run from the repository:

```powershell
.\.venv\Scripts\python.exe -m hanni.dashboard.cluster_credentials --node hanni
```

The command prompts without echoing. Use `--all` for the active roster sharing a
password, or `--data-dir` for an explicitly different HANNI data directory.
It reads the same environment/`.env` data-directory setting as the launcher.
Credentials remain in this Windows user's vault and are not part of Git commits
or the portable native client.

## Verification and live blocker

- Frontend type/production build PASS, including the updated confirmation.
- All 75 focused cluster/power/credential/terminal tests PASS. New regressions
  cover private password stdin, non-root sudo even when policy listing needs no
  password, root inhibitor override, readonly exact-command authorization, four
  concurrent submissions dispatching once, missing/malformed vault values,
  data/node isolation and safe Tailscale sign-in diagnostics.
- Original browser harness: all 24 checks PASS at twelve widths, including
  Cancel/Escape, accepted/failed simulated power responses and unavailable nodes;
  no JavaScript/CSP/external-request errors. Simulated requests do not prove a
  physical reboot.
- Final full Python suite: **882 passed, 2 skipped, 17 subtests**, 55.40s.

Read-only live `sudo -l` checks reached an actual external blocker: all eight
Tailscale SSH sessions require an additional authentication check (SSH exit255).
Root and ordinary accounts both require the fresh sign-in. This occurs before
remote sudo execution, so it does not establish whether the supplied sudo password
is accepted on each machine. Credential presence was verified without printing
values. No node was rebooted or suspended by verification.

The UI now explains this condition: open the node's **SSH Terminal** and complete
Tailscale's browser authentication check. HANNI retains existing tailnet policy;
it does not bypass the check or accept unverified host keys. Sign-in URLs are not
exposed or persisted in node/API status. The authenticated user can then retry the
confirmed reboot after fresh telemetry and power authorization arrive.

Read-only evidence: `data/hanni-phase12-review/reboot-fix/authorization.json`.
The first probe-helper attempt failed locally during dotenv discovery from stdin
before contacting nodes; the corrected explicit-path helper produced the retained
eight-node report. This helper error is not counted as a passing live check.

After the owner completed the Tailscale sign-in on 2026-10-09, a new read-only
check succeeded for all eight active roster nodes. Each native Tailscale SSH
connection authorized the root account and confirmed systemctl availability for
the fixed reboot command; the runtime therefore uses its existing direct-root
execution path. Credential presence was retained, but these root checks do not
test whether the saved sudo password is accepted by ordinary accounts. No reboot
or suspend command was invoked. Yunjin remains excluded under repair.
Follow-up evidence: `data/hanni-phase12-review/reboot-fix/authorization-after-signin.json`.

Restart HANNI's dashboard/controller process to load the backend fix, then reopen
or refresh the desktop frontend. Opening the desktop alone attaches to an existing
backend and does not reload its Python modules. The native wrapper has no source
change and serves the newly rebuilt frontend from this repository.

## References

The inhibitor override is defined in the
[official systemd command documentation](https://github.com/systemd/systemd/blob/main/man/systemctl.xml).
Sudo's stdin and policy-list options are documented in the
[official sudo argument implementation](https://github.com/sudo-project/sudo/blob/main/src/parse_args.c).

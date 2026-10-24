---
name: windows-ssh-remote-dev
description: Edit and test Windows repos remotely over SSH from Linux.
version: 1
author: hermes
license: MIT
metadata:
  hermes:
    tags: [windows, ssh, remote, tailscale, hanni]
    related_skills: [mcp-server-selftest, github]
---

# Windows remote dev over SSH from a Linux host

## When to Use
The target code lives on a Windows machine and the agent runs on a Linux host; work happens over SSH (Tailscale). Covers inspecting, editing, running, and testing remote repos.

<owner>'s laptop: `qu4lz@<tailnet-ip>` via Tailscale, key `~/.ssh/id_ed25519_laptop`, repos under `C:\Projects` (HANNI is in `C:\Projects\HANNI_NEGATIVE_SIGNALS_LLM_FINAL_ROUTING`).

## Connection & shell
- Remote default shell is `cmd.exe`. One-liners fine; anything complex wrap in `powershell -Command "..."` (escape `$_` as `\$_` through ssh double quotes).
- Unix text utilities are absent remotely — use `findstr`, `Select-Object`, `Get-Content -Tail` instead.
- `find /c "x"` exits 1 when the count is 0 — it silently breaks `&&` chains; put it last or use `;`.

## File transfer (both directions)
- scp tends to fail here; use tar over ssh instead:
  - pull: `ssh host "cd REPO && tar cf - path1 path2" | tar xf -` (into a local scratch copy — edit locally with read_file/patch, far more reliable than PowerShell string surgery).
  - push: `tar cf - files | ssh host "cd REPO && tar xf -"`.
- For reading big remote files, pull a scratch copy and read locally rather than paging through PowerShell.

## Long-running remote jobs
- A foreground `ssh "python long_job.py"` that hits the local tool timeout usually keeps running remotely — treat timeout as "still running", then poll for the job's report/output file with short ssh calls (`for %F in (...) do @if exist %F (@echo %F %~zF)`).
- `start "" /b` detachment through ssh is unreliable (sometimes never launches). WMI `Invoke-CimMethod -ClassName Win32_Process -MethodName Create` reliably survives session close — but see artifacts below before trusting its results.
- Write results to a report file on disk and poll it; never rely on stdout surviving the connection.
- Flush stdout (`print(..., flush=True)`) in remote jobs — redirected stdout is block-buffered and a killed process loses everything.

## Launch-context artifacts (classify before debugging)
Processes started via ssh or WMI are NOT in the interactive desktop session. Their failures are artifacts, not tool bugs:
- `CredRead (1312, 'A specified logon session does not exist')` — Windows Credential Manager is per-interactive-logon; Google/Gmail OAuth caches are unreachable. Runs fine when the user's own app spawns the process.
- "no visible window" / "did not report a foreground window" / `Start-Process ... Access is denied` — no interactive window station (WMI even lands in session 0). UI enumeration, window focus, and desktop launches all fail.
- PowerShell child failures like "module 'Storage' could not be loaded" when you passed a hand-built env block — include `SYSTEMDRIVE`, `WINDIR`, `PSModulePath`, not just `SYSTEMROOT`/`PATH`.
Report these as launch-context artifacts and recommend verifying inside the user's own session; do not chase them as code bugs.

## Git on a repo with massive uncommitted work
- Checkpoint first (`git add -A` after a `--dry-run` scan for secrets/model weights/archives), then only targeted edits — no checkout/reset/stash/branch-switch while the user's work is uncommitted.

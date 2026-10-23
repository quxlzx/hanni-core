# Docker model migration — 2026-10-12

## Actual outcome

**HANNI: three models migrated and live-verified. Wonyoung: Strata remains native pending administrator Docker installation.** All four endpoints passed health through HANNI's original authenticated/registered inference boundary after the HANNI cutovers. No model weights, default model, context settings, privacy authorizations or existing endpoint exposure were changed. No models or external container base images were downloaded.

| Model | Before | After | Live check |
|---|---|---|---|
| Nex N2 Mini / P6000 | Native user systemd | `hanni-model-nex`, Docker | Alias verified, answer `7`, port 8102 |
| Mellum 2.1 / P40 | Native user systemd | `hanni-model-mellum`, Docker | Alias verified, answer `7`, port 8103 |
| Swift 1.5 / RX 9060 XT | Native user systemd | `hanni-model-swift`, Docker | Alias verified, answer `7`, port 8101 |
| Flash Next / Strata / RX 7900 XT | Native tmux/Python on Wonyoung | Native, unchanged | Original boundary reports healthy |

Post-cutover inspection found exactly one llama-server process for each HANNI alias, matching its running container PID. Each container runs as UID/GID 1000, with a read-only root filesystem, dropped capabilities, no privilege escalation and read-only model/binary/library mounts. Docker restart policy is `no`; original user systemd units remain the sole restart/lifecycle owner, so Control Center's existing unit operations remain valid. Model ports remain bound to 127.0.0.1. Host networking preserves the original loopback interfaces; these inference containers are not untrusted task sandboxes.

The image is a tiny locally imported empty runtime filesystem. Existing host binaries and libraries are mounted read-only rather than replaced with a different CUDA/ROCm/Vulkan build. This preserves the original Pascal-compatible CUDA build and installed driver libraries; **it is deliberately host-dependent and is not a portable self-contained image**. Model files remain in their original host locations. GPU selection remains the original physical GPU: UUID selection for Nex/Mellum, and identity-verified Vulkan mapping for Swift. The RX 9060 XT appears as Vulkan1 natively and Vulkan0 in the container, so the Docker command remaps that index; it does not select the integrated GPU.

Original units are untouched. Migration backups and wrappers are under `/home/user/hanni-control/docker-migration/`; overrides are only `~/.config/systemd/user/hanni-{nex,mellum,swift}.service.d/50-hanni-docker.conf`. The active wrapper is `hanni_migrate_v3.py`. Model, context, KV types, parallelism, flash-attention, fit/offload settings and existing service logs are retained. CUDA device passthrough currently exposes the host NVIDIA device nodes while selecting the intended UUID; it is not a security isolation boundary between the GPUs.

## Failure retained and corrected

The first Nex cutover failed because the systemd manager inherited a Docker endpoint pointing at an unavailable Podman socket. It timed out and restored the native Nex unit; native recovery was checked before retry. The corrected launcher explicitly targets `unix:///var/run/docker.sock`, validated from a transient user systemd unit, and detects a failed unit before its readiness deadline. Subsequent Nex, Mellum and Swift cutovers passed. The initial failure, native recovery and successful retry are retained in local evidence; they are not presented as a first-attempt pass.

Health and a single arithmetic response establish endpoint operation, not model-planning quality or autonomous-goal completion. Prior Mellum correctness failures, Swift residency limitations and the Phase 2 completeness failure remain. No benchmark promotion, unattended task family or private remote-context expansion was enabled. Reboot recovery, prolonged load, full latency regression and Docker daemon failure recovery are **NOT TESTED**.

## Control Center process reporting

Systemd's MainPID is now a Docker client, so treating its RSS as model RSS is inaccurate. The updated `backend/controller.py` identifies only fixed container names with exact `org.hanni.service` and `org.hanni.owner=control-center` labels, then reports the actual running model PID alongside `unit_pid`. Foreign labels cannot replace the native PID. Nine offline Control Center tests passed, including the new ownership tests. A staged candidate was also run on HANNI against the actual three containers and returned their real PIDs/RSS.

This PID-reporting source fix is **staged and validated, not loaded by the running Control Center**. Its existing lifecycle controls still use the original systemd units; until the controller is redeployed through its normal procedure, per-process RSS may reflect the Docker CLI. No Control Center service restart was performed. The source patch preserves protected Strata lifecycle checks.

## Wonyoung prerequisite and remaining work

Wonyoung has no Docker, no passwordless sudo, no `newuidmap`/`newgidmap`, and restricted unprivileged user namespaces. Rootless installation cannot proceed under the current account. Docker's documented rootless prerequisites include those mapping helpers, and Ubuntu's namespace restriction requires an appropriate AppArmor configuration. [Docker rootless requirements](https://docs.docker.com/engine/security/rootless/), [Ubuntu rootless troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/).

The inspected Ubuntu package index offers `docker.io` 29.1.3-0ubuntu4.1. The owner chose to run the prepared administrator prerequisite and report completion:

```sh
sudo sh /home/user/hanni-control-agent/docker-migration/wonyoung-install-docker.sh
```

That reviewed script installs the distribution Docker package, grants `wonyoung` Docker-group access and starts/enables the Docker daemon. Docker-group membership grants administrative power over the machine. It does not stop or migrate Strata. No password, key or token should be sent in chat. Reconnect SSH afterwards so new group membership takes effect.

`strata_run.py` is staged at `/home/user/hanni-control-agent/docker-migration/strata_run.py`. It preserves installed Strata, both GGUF shards, expert packs, MTP data, the original protected configuration/authentication and ROCm SDK/Tensile paths. It mounts code/models read-only, the existing log writable, and the original AMD devices; it refuses to start while port 8080 is occupied. The original configured bind 0.0.0.0:8080 is preserved; no new public binding is added. Its container GPU/startup behavior is **NOT TESTED** until Docker is available. AMD documents exposing `/dev/kfd` and the appropriate render device for ROCm containers. [AMD container GPU access](https://rocmdocs.amd.com/en/latest/install/docker-containers.html).

After the administrator finishes: verify Docker access and AMD GPU discovery without loading a second model; inspect existing Control Center agent start/stop behavior; back up its exact native launch; confirm no active inference; stop only the exact original Strata process through authorized lifecycle scope; start the prepared container; verify authenticated endpoint/model identity, context, real inference, logs and one process; integrate the original agent's launcher; restore the native launch immediately if a required gate fails. Do not merely execute the launcher against the currently occupied port. No success is claimed for these pending steps.

## HANNI rollback

Rollback each affected model independently as athena on HANNI:

```sh
python3 /home/user/hanni-control/docker-migration/hanni_migrate_v3.py rollback nex
python3 /home/user/hanni-control/docker-migration/hanni_migrate_v3.py rollback mellum
python3 /home/user/hanni-control/docker-migration/hanni_migrate_v3.py rollback swift
```

Rollback stops only the selected unit/container, removes only the migration override, reloads user systemd, clears that unit's failure/start-limit state and starts its untouched original native unit. Verify health/model identity afterwards. It does not delete models, original units or backups, and does not reset Docker globally. Live rollback was exercised for Nex during the failed initial attempt; the updated manual rollback paths for all three are not separately live-tested.

Reproducible evidence is under `data/docker-migration`: GPU preflights, original inventory, successful cutover receipts, final container/process inspection, original-boundary health and candidate controller PID observations. Exported evidence excludes credentials and verbose unrelated host/runtime information. The bundled source is for review/recovery; migrating already converted services again is refused rather than silently replacing their overrides.

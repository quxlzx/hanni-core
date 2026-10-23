# Sandbox live readiness — 2026-10-12

**Activation blocked. No deployment or infrastructure changes were made.** The owner asked to use an existing cluster, inspect its actual state and report the control plane, kubeconfig and nodes before deployment. Existing authorized SSH/Tailscale access was reused. No credentials, private keys or kubeconfig contents were copied or requested. No cluster installation, service restart, networking change or model request was performed.

## Discovered state

- **Kubernetes control plane: NOT IDENTIFIED.** The seven reachable Linux nodes had no `k3s`/`kubectl` executable on their reported PATH, no running `k3s`/`k3s-agent` systemd service, and no standard kubeconfig discovered. No MicroK8s, k0s, RKE2 or Minikube executable was reported. This is evidence from the inspected locations, not proof against every possible custom installation.
- **Kubeconfig location/context: NOT FOUND / NOT VERIFIED.** HANNI reported no KUBECONFIG environment reference; standard `/etc/rancher/k3s`, `/var/lib/rancher/k3s` and `/etc/kubernetes` locations were absent. Bounded read-only searches of owner homes, `/etc`, `/opt` and `/srv` found no `kubeconfig`, `k3s.yaml`, `admin.conf` or `.kube/config`; those searches did not hit their directory-count cap.
- **Shared sandbox storage: NOT FOUND** at `/srv/hanni/shared/sandbox` on the seven reachable nodes. HANNI also lacked `/srv/hanni/shared`; the inspected `/mnt`, `/media` and `/srv` locations had no corresponding shared mount.
- **Agent cluster repository: FOUND LOCALLY** at `C:\Users\user\hanni-agent-cluster`, not in the searched remote locations. It contains README, a FastAPI `/health` application and requirements. Its `infrastructure/k3s`, other infrastructure folders and configuration contain `.gitkeep` placeholders. No Kubernetes manifests, endpoint gateway, node enrollment or kubeconfig were found there. The README reports networking in progress and an older roster naming Yunjin as infrastructure; this is historical documentation, not current deployment proof. No files in that repository were changed.
- HANNI has Docker and Podman; its Docker security options reported AppArmor/seccomp/cgroup namespaces. No running Kubernetes-image candidate was found. That does not establish gVisor/Kata isolation or an operational Kubernetes cluster.

| Node | Current observation | Kubernetes status |
|---|---|---|
| HANNI | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Wonyoung | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Haerin | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Chaewon | Tailscale reports offline; SSH probe unavailable | NOT VERIFIED |
| Minju | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Wonhee | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Jeongyeon | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Karina | Authorized read-only SSH succeeded | Standard components/config absent; not enrolled/Ready verified |
| Yunjin | Protected maintenance; no registered SSH binding | NOT TESTED |

SSH reachability is not Kubernetes node readiness. The source's proposed `hanni-k3s` context, namespace, worker labels and storage claim remain unverified. Chaewon could host inaccessible infrastructure; Yunjin's historical role could explain missing access, but neither inference establishes a real control plane. Neither host was awakened, reconfigured or taken out of maintenance.

Raw read-only receipts remain in `data/cluster-harness-validation/readiness-final.json`, `hanni-infrastructure-discovery.json` and `kubernetes-location-discovery.json`. An initial probe harness TypeError was corrected and its original receipt preserved as `readiness-harness-error.json`; it was not classified as an infrastructure failure. The earlier source archives and model failures remain intact.

## Local fixes completed while activation is blocked

Sandbox pods now request their full 4 GiB memory limit, avoiding admission of two 4 GiB jobs based on 1 GiB requests on smaller workers. Coding tasks require explicit owner `check_files` from the approved source snapshot. The worker restores those checkers immediately before running them, refuses symlinked checker paths, records their SHA256 and exits unsuccessfully when selected checks fail. A test actually weakens a checker for an incorrect program, restores the owner's checker, and verifies the incorrect program fails while the corrected program passes. These fixes do not enable deployment or modify production defaults.

Final local regression: **162 passed, 13 subtests passed, two skips** (4.48 seconds). Skips were the optional LangGraph module in the ordinary environment and unavailable Windows symlink creation. The previously separate real LangGraph checks used controlled provider seams; no live external harness or first supervised Kubernetes job has run. Native remote tool-call support, private gateway connectivity, research/embedding backend, model admission evidence and independent goal acceptance remain separate failed/unverified gates.

Reproduce the read-only inventory without overwriting prior receipts:

```powershell
.venv\Scripts\python.exe scripts/inspect_sandbox_readiness.py --output data/cluster-harness-validation/readiness-reproduction.json
powershell -NoProfile -File scripts/check_cluster_harnesses.ps1
```

The output filename must be new. The inventory reads executable/config-path metadata and existing services only; it never displays certificate/token contents or starts services.

## Required next evidence

Provide an actual existing control-plane access reference or kubeconfig location/context. If the control plane is on Chaewon or Yunjin, existing authorized access must first be available; maintenance and service changes remain outside these read-only checks. Then query actual Kubernetes nodes, namespace/security controls, storage and runtime/CNI behavior before submitting any task. Do not infer a Kubernetes deployment from the SSH roster, create a replacement cluster, or weaken permission/resource/quality gates to activate the candidate.

# HANNI V3.7 distributed compute implementation

## Scope and baseline

The manager coordinates one engineer and one independent verifier. Implementation
extends the original WorkflowService analysis dispatch; the original planner,
ToolRegistry, permissions, invocation receipts and completion verification remain
authoritative. Remote model servers receive approved inference input, never tool
authority or arbitrary shell access.

Work starts from commit `3cf6a09`, whose V3.6 regression baseline was 1,667 passed,
two skipped. The implementation branch is `codex/hanni-v3.7-distributed`.
No deployment addresses, credentials, private discovery artifacts or user model
archives belong in these checkpoints. No push is authorized.

## Checkpoints

| Milestone | Current evidence and status |
| --- | --- |
| M0 architecture and safety | Existing workflow authority inspected; three actual agents assigned; protected local deployment roster created with owner-only ACL; independent protocol sealed before implementation scoring. |
| M1 secure nodes | Eight nodes authenticated through existing Tailscale SSH; LAN is preferred only after strict host verification. Private census lives under `data/v37-manager/discovery`. Cluster roster migration is complete. 83 focused monitoring, power, terminal, vault and protected-deployment regressions pass; no live power operations were performed. |
| M2 GPU inference | Separate P6000/P40 24 GiB devices, CUDA sm_61 backend and existing 27B Q4_K_S weights independently verified. Both passed two exact near-limit retrievals at each of 8K, 16K and 32K. IQ3_S weights are missing; 128K FP16 preflight exceeds physical VRAM. Bounded 64K results remain separate. |
| M3 Strata | Original installation, launcher, source, config and model retained. Actual API, two small requests and two near-8K exact retrievals pass; original cache-accounting FAIL and corrected erratum preserved. Accepted capacity 8,192. Owned cohort process closed and original independent service unchanged. |
| M4 registry | Strict protected configuration, actual observations and durable model/device/KV-bound context receipts. Three workers registered with synthetic-only production approvals. Missing or changed evidence cannot advertise verified capacity. |
| M5 scheduler | Original analysis seam connected to bounded scheduling. Independently audited original three-worker workflows: 39.407 s sequential, 10.203 s parallel; 3/3 analysis jobs and 4/4 steps verified in each. Disclosed planner fixture and mixed cache state limit the performance claim. |
| M6 recovery | Durable receipts/events, safe reassignment, cancellation and original-authority crash reconciliation pass independently. Auxiliary readers cannot invalidate live jobs; Windows compute-root junction escapes fail closed. No external action replay. |
| M7 desktop | Existing Cluster, Models and Workflows extended. Independent native grades 8.8/8.7/8.8; template 1.0 each. Final repaired three-worker preview passed 11 controls, six physical captures, no errors. |
| M8 full verification | Frozen production source: 1,728 passed, two skipped; 41 independent checks and 69 focused repair checks pass. Actual streaming and three-worker outputs independently verified. Both allocated 64K trials timed out at 300 seconds, so accepted GPU capacity remains 32K; owned sessions closed. Overall PARTIAL includes missing IQ3_S, 128K memory, original 4B planning and credential-output incident. |

## Local evidence

The independent verifier sealed protocol hash
`1712c95f1132c1bf25fbf3dfbd24f581f88c328e9fa32b6a312780af9c266eb3`.
Hardware discovery is read-only and bounded. Controlled HTTP tests demonstrate
scheduling and security behavior; they do not establish GPU inference performance.
Missing or untested context, throughput and resource measurements remain unknown.

Deployment lives in the ignored local data directory at `compute/deployment.json`.
An unconfigured deployment starts disabled. This owner deployment now registers
the three measured workers for synthetic probes only. Existing cluster addresses
are retained there rather than in source. Private categories require
explicit per-worker approval; connectivity never supplies that approval.

Large model downloads, software installation, startup-service changes and
unrelated LAYA/memory changes are outside this implementation. Only processes
started and identified by this implementation may be stopped by its lifecycle
controls. Independently managed services remain under their existing owner.

# HANNI V4.4 system inventory

Inspected baseline: `80ab843`; V4.4 validation release target: `0.14.0`.
The current deployment is inspected through its original configuration and
protected transports. Existing files and prior reports are not new test passes.

| Component | Integration inspected | Current evidence and limitation |
| --- | --- | --- |
| V3 workflows | Original `WorkflowService`, registry/host, lease fencing, plan review, original verified handlers and durable outcome checks | 64 fresh manager service/store/security/outcome checks passed. Model replies and provider seams are controlled; deployed autonomous planning quality is not established by these tests. |
| Memory | Original store, `MemoryAwareSession`, scoped recall, context/provider integration and current record provenance | 16 fresh manager memory integration checks passed. Durable memory is enabled; enhanced context is disabled in deployment. No owner memory is used as synthetic data. |
| LAYA | Optional read-only advisory, separate quality/privacy gates, deterministic retrieval fallback and controller-bound Stop | 23 fresh advisory compatibility checks passed. Advisory/retrieval are disabled; no deployed LAYA model quality or measured benefit is established. |
| MCP Hub | Original dynamic registry, transport/schema approval, original permissions and original-controller attachment | 24 fresh manager MCP checks passed with isolated protocol/provider seams. External account/service integrations are not declared connected from fixture success. |
| Distributed inference | Protected `ComputeRegistry`, original `InferenceTransport`, bounded scheduler and workflow receipt reconciliation | Fresh primary health succeeds; all three remote workers are unavailable. Direct scheduler defects were reproduced before repair. Live remote stress and hardware performance remain blocked. |
| V4.0 routing | Original adaptive engine/client wrapper, eligibility, fixed endpoint admission and measured category profiles | Configuration remains balanced with identity-bound evidence thresholds. Current controlled and final live evaluation results must be recorded separately. |
| V4.1 collaboration | Workflow analysis binds the original collaboration engine; source verification remains independent of consensus | Secondary endpoints are unavailable. Controlled correct/incorrect consensus, failures and evidence conflicts do not establish actual multi-model improvement. |
| V4.2 performance | Original compatible-worker queue ordering, per-endpoint observations and memory/profile caches | Existing historical reports describe prior measurements. Fresh bounded stress/regression evidence is required for V4.4; no GPU throughput or cache gain is inferred from code presence. |
| V4.3 Model Lab | Original registry/admission/evaluation adapters, persistent manifests, scoped audited controls and exact serialized exports | Prior source-matched V4.3 verification exists. Fresh native/backend checks are part of V4.4 and must not be substituted by old screenshots. |
| HANNI OS | Actual Windows Forms/WebView2 desktop and original dashboard APIs | Existing application and model processes are external and preserved. Native review uses a separate bounded current-source dashboard; a normal restart is needed for the existing old backend to load repairs. |

Fresh focused manager baseline: **127 passed in 50.96 seconds**, no errors or
failures. Its XML and module summary are private under `data/v44-manager`.
Full regression, independent live responses and desktop review are separate
milestones recorded in [checkpoints](HANNI_V4_4_CHECKPOINTS.md).

Fresh configuration retains assisted workflows, two bounded parallel reads,
two active workflows and one safe retry. MCP is read-only with three model
tool rounds. LAYA remote text and stored-memory sharing are disabled. Critical
RAM admission and the primary's one serving slot remain in force.

The local configured supervisor is `Qwen3.5-4B-Q4_K_M.gguf`, not an assumed
custom replacement. Fresh protected properties report 16,384 allocated context;
that does not independently prove context understanding or a 128K allocation.
The initial host sample reports 75.3% RAM use and an 8,151 MB RTX 5060 Laptop GPU.
P40/P6000/Strata current installed files, loaded models and resource capacities
remain unknown while their protected access fails. No remote service is started
or independently managed process terminated by this inventory.

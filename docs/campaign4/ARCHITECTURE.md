# Inspected V3 workflow architecture

The current engine retains the original capability registry and MCP host.
WorkflowPlanner uses two bounded model passes: an outline with verification
criteria and dependencies, then capability/argument bindings drawn from each
step's routed menu. Trusted code validates the graph, schema, typed references,
policy and definition fingerprints. A model proposal cannot provide execution
authority. Controlled planning responses exercise these contracts; actual
semantic goal understanding and plan quality require real model responses.

WorkflowService owns scheduling and dispatch. Known local safe reads may run
in parallel within the configured bound. Writes and other execution classes
retain separate admission rules. Dependencies require verified predecessor
results. Original host argument preparation, registry permission checks and
action verification remain in the execution path.

WorkflowStore persists steps, invocations, approvals and checkpoints in SQLite.
An owner lease and fencing generation prevent obsolete runners from committing
results. Invocation identity and consent are persisted before dispatch. Review
binds the plan, exact arguments and current capability definition. Managed
report writes require reviewed scope; other supported writes need an exact
action approval. Cancellation or pause withdraws future admission, including
the final original-registry execution guard.

Synchronous handlers already executing cannot safely be killed. They remain
visible as active until return. Cancellation testing therefore distinguishes
an already admitted effect from an unauthorized new dispatch after withdrawal.
It does not promise to undo a completed write.

Retries are restricted to explicitly safe local reads and the configured
bounded budget. Restart recovery preserves verified steps and abandoned
invocations. A safe interrupted read requires explicit resumption; an uncertain
write is retained for reconciliation and cannot license automatic replay.
Reports and completion states depend on verified criteria and original
readback, rather than a successful acknowledgment alone.

The declared transition map is a store-level allowed-state contract. Native
scheduler/control coverage is reported separately, with actual observed
receipts. Directly constructing a stored state does not prove that the
controller naturally reaches that state.

The new pre-dispatch control reproduction exposed a state-reporting defect in
the worker exception branch: the original dispatch guard refused the tool,
but the catch path replaced pause/cancel with a generic blocked state. The
repair reuses existing control settlement after retaining abandoned/uncertain
receipts. Approval, fencing and replay behavior must remain independently
verified through that changed path.

Continuation now checks unresolved invocations independently of scope freshness.
A valid approval cannot authorize resuming past an uncertain result. Both API
controls and user-facing availability require reconciliation before resuming
or requesting a safe retry.

The planner also compares literal local read resources against explicit owner
source paths. This checks objective retention separately from permission:
owner review of a substituted plan previously authorized that read but did not
make it the originally requested source. Typed prerequisite references retain
their original verification and schema gates. Source-free objectives and
supported source-path syntax remain separately tested.

Typed reference validation now checks only the requested kind. Exact bounded
JSON integers remain integers even when they exceed float range; unsupported
finite-number conversion fails through the existing typed workflow error.

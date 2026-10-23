# Workflows interface: implementation and verification contract

This is an implementation contract, not a completed browser or native acceptance report. The UI extends the existing graphite desktop shell and original authenticated dashboard. Opening Workflows starts neither a model nor a tool.

## Implemented interface

The overview reads `/api/workflows?limit=50` with the existing private token. Search and status filters apply to the loaded history, with explicit active, awaiting approval, attention, paused and terminal views. Each row shows the recorded state, aggregate evidence status, verified step count and last checkpoint. Detail reads the selected private workflow ID and is remounted when the selection or token changes, preventing old detail data from appearing under another workflow.

Goal submission defaults to Assisted. The form uses the server's configured goal-length bound and explains each autonomy mode. It does not grant tool authority. The detail shows the original goal, actual plan/dependencies/criteria, persisted step attempts and states, verification scopes and acceptance checks, last checkpoint, invocation history, bounded output excerpts and artifact records. Elapsed time uses the persisted first start and finish boundaries and therefore includes pauses; it is not CPU time.

All mutations use the fixed `/api/workflows` operation gateway. A synchronous request ledger rejects simultaneous duplicate clicks, retains the UUID for an identical explicit retry after an ambiguous response failure, and changes it when the operation or data changes. It clears successful attempts and invalidates old responses after token rotation. There is no automatic mutation retry.

Plan approval displays the captured plan, planned arguments, dependencies, completion criteria and limits. Typed predecessor references remain visibly planned inputs. Action approval requires prepared resolved arguments and displays those exact captured values and the tool-definition binding. Both plan and action reviews retain their captured approval record, revision, plan/action/definition hashes and expiry. Polling never silently rebinds an approval. A changed or expired review disables its confirmation. Approval, rejection, revocation and safe retry use their specific selected approval or step IDs. Backend controls and reasons remain authoritative; a disconnected, stale or unattached runner disables mutations.

Pause and cancellation requests remain distinct from confirmed paused/cancelled states. Noninterruptible action copy explicitly says the current action may continue. Revocation does not claim to undo completed work. Viewing an output renders saved text only, without opening a file, URL or tool.

Existing notification Inspect permits the `workflows` target and consumes only the stable workflow ID. Notification read/dismiss operations never approve a workflow action.

## Public selectors

| Surface | Selector or accessible name |
| --- | --- |
| Overview | `.workflows-page`, `Search workflows`, `Workflow status` |
| Goal form | `New goal`, dialog `New workflow goal`, `Goal`, `Autonomy mode`, `Create workflow` |
| Workflow row | `.workflow-row[data-workflow-id]` |
| Selected detail | `.workflow-detail[data-workflow-id]`, `Back to workflows`, `Refresh workflow` |
| Step | `.workflow-step[data-step-id]` |
| Approval record | `.workflow-approvals [data-approval-id]` |
| Plan review | `Review plan approval`, dialog `Approve this workflow plan?`, `Approve this plan` |
| Action review | `Review action`, dialog `Approve this workflow action?`, `Approve this action` |
| Safe retry | `Retry this safe failed step`, confirmation `Retry this safe step?` |
| Revocation | `Revoke approval`, confirmation `Revoke this approval?` |
| History | `Checkpoints and tool activity` |
| Saved output | `View output`, dialog prefix `Output:` |

## Verification status at initial source readiness

Frontend typechecking passed. Sixteen Node tests exercise actual helper/request state transitions: server controls, required live controller/runner/token and fresh data, expiry boundary, changed bindings and missing prepared arguments, immutable review revisions, independent pending-plan expiry, per-record revocation, exact fixed mutation payloads, selected-step retry, canonical status filters, timestamp duration semantics, synchronous duplicate locking, failed UUID reuse, successful UUID clearing and token rotation. Confirmation rechecks the current clock synchronously at the click boundary, rather than relying on the last one-second render tick. Offline and submitting states are explained inside the modal. The existing twelve MCP frontend tests also passed.

These tests are not interaction or screenshot proof. Genuine manager-backed browser tests and independent native screenshots remain pending until the backend and compiled frontend are coherently frozen. The authored `scripts/v3_review/check_browser.py` uses the production private gateway, WorkflowService and original registry with disclosed isolated files, scripted two-pass model replies and resource telemetry. The original fixture host retains read-only mode and explicitly whitelists `file.write` only to exercise exact personal-file approval; original owner/risk/confirmation gates remain real and production configuration is untouched. A single test window's clock is advanced to test click-time expiry without altering backend approvals. Real accepted HTTP responses are aborted to test ambiguity; no private CRUD response is fabricated. The draft covers actual goal creation, plan approval, sensitive action review/reject, persisted result/artifact viewing, another window's revision changes, expiry, first-fetch failure, cold history, notification Inspect, duplicate-response UUID retry and keyboard modal behavior. Revocation, supported safe retry and pending cancellation still require genuine final-service interaction coverage. The independent verifier assigns the native visual score; implementation does not self-grade.

The later actual [browser cycle 6](browser-cycle-6.md) passed all sixty checks, including exact sensitive approvals/rejection, lost-response reconciliation, pending-plan revocation, explicit safe-read retry and pending cancellation. Its expiry clock uses a dedicated browser context so sibling windows remain independent. The report retains all earlier failures and describes synthetic telemetry/model seams separately from the real private gateway, original service and actual handlers. Native visual/lifecycle review and configured-model scoring remain independent final requirements.

The interface does not create a resumable conversation approval queue, a cluster executor, an unrestricted shell, background work while the computer is asleep, or an arbitrary file-opening endpoint. An artifact's verification and a successful tool response remain distinct from whole-goal acceptance criteria.

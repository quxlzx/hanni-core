# Workflows browser cycle 7: settled-status copy repaired

The actual frozen-bundle headless cycle passes all 62 checks, exit 0. Evidence is retained in `data/hanni-v3-review/browser-cycle-7/browser-review.json`. The previous five failed browser cycles, accepted cycle 6 and failed native cycle 2 remain preserved; no visual score is assigned here.

Independent native review found a real copy defect: authoritative Paused and Cancelled records retained persisted pause/cancel request flags, and the UI described those already-settled requests as future boundary work. After checkpoint `f7e88aa`, the authorized frontend-only repair adds `workflowBoundaryNotice`. Known unsettled states retain pending request text. Paused and terminal states omit it when no action is active. An observed `active_uninterruptible` call always retains the explicit noninterruptibility/pending-outcome warning, including alongside a settled status. Unknown future states do not invent pending work.

No backend, configuration, permission, approval, persistence, handler or stylesheet change is made by this repair. TypeScript check and production build pass. The helper suite passes all 31 tests: twelve existing MCP cases, sixteen existing workflow cases and three new cases covering settled flags, all known unsettled states and preservation of the active noninterruptible warning.

The same actual private HTTP/original-service/host/registry browser control and outcome checks from cycle 6 pass unchanged. Two additional assertions wait for the UI's authoritative Paused or Cancelled label, then establish that its respective pending request and future-boundary text are absent. The actual revoked approval and cancelled action remain persisted, and the unchanged side-effect oracles pass. All seven isolated workflow scenarios, exact approvals, lost responses, safe retry, stale/cold history and twelve responsive widths are exercised again. No JavaScript errors or nonlocal requests are recorded. Runtime bytes remain frozen through the cycle.

| Artifact | SHA256 |
| --- | --- |
| Compiled app.js | `18db56d576d491437aef99c014740cb7829142e4e5a2e9f297fbd790cbcf31ef` |
| Unchanged style.css | `76c1e4d5c353b93acf71f02cf40de00d11f03515aae2a3930e9f31d675333e4e` |
| workflow_types.ts | `5a3cb6757b33efd9b82aa3867e015fa2aa30d5316b9bc762600f5f9315fc70da` |
| workflows.tsx | `5c472fa747ca3d6ed74e7ea48b887ebf3dd3259bd294ef001e3a016496a4af99` |
| Browser harness | `8e37c42af0afb2e6ae406fd42e664a1445891f1df10f08209a2906ab3d2026ca` |
| Production Python manifest | `29a1478efffdaa0ec49d78e4b43f6bb2a3f8e5a77a586e0ac3f59326188ebbec` |

Fixture limits remain those recorded in [cycle 6](browser-cycle-6.md): scripted two-pass planning, synthetic cached telemetry, original handlers against isolated real files/stores, disconnected providers and an explicit fixture-only original file.write allowlist. Client expiry, pending cancellation and browser layout are bounded exercised claims, not server-expiry, interruptibility, natural-language planning or native visual acceptance. No native window/model/provider/voice/node operation is launched in this repair cycle. Independent native recapture and grading remain pending.

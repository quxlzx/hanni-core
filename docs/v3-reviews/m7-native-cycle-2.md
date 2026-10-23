# M7 independent native review — cycle 2

**FAIL: actual settled workflows retain misleading pending-stop copy.** Native functional harness: **203 checks passed, 106 real framed screenshots, zero JavaScript errors, zero nonlocal browser requests and zero harness errors**. Overall subjective visual score **8.70/10**, AI-template score **1.0/10**. The score does not override the independent functional/truthfulness defect required by V3 section 17.

This is the original portable application, not Chromium screenshot emulation: launched window PIDs 38548 and 31276 were checked against their owned process trees. All four physical sizes were observed exactly: 1920×1080, 1440×900, 1366×768 and 900×650 at **120 DPI / 125%**. Twenty-one actual interface states were captured at all four sizes, plus 22 supplemental frames showing lower dialog buttons, expanded criteria and outputs. The reviewer inspected all 106 frames in labelled diagnostic contact sheets derived from the unchanged captures, and opened representative full native frames for approval arguments/actions, compact verified steps, overview, settled pause/cancel and saved output. Contact sheets are only inspection aids; the raw framed PNGs and recorded geometry are the evidence.

V3 specifies a subjective overall threshold above 8.5, with no exact weighted categories. For continuity with earlier desktop reviews, this review explicitly uses the prior desktop rubric rather than calling those weights a V3 requirement:

| Dimension | Maximum | Score | Pixel and interaction basis |
|---|---:|---:|---|
| Typography and hierarchy | 2 | 1.75 | Clear headings and labelled evidence; long full-path goals occupy several lines and repeat in reviews. |
| Layout and information density | 2 | 1.70 | Useful table-to-stacked-row adaptation, evidence/dependency details in disclosures; compact detail requires substantial vertical travel. |
| Spacing and consistency | 2 | 1.78 | Stable aligned controls, restrained separators and predictable dialog spacing at all observed sizes. |
| Professional visual identity | 2 | 1.80 | Existing graphite desktop shell and plain operational records; no gradients, fabricated activity or marketing decoration. |
| Desktop integration | 1 | 0.92 | Genuine native frame, exact DPI/sizes, owned close/reopen and retained backend/history. Other DPI settings were not tested. |
| Interaction quality | 1 | 0.75 | Real approvals, rejection, retry and stale gates work; pending-stop copy incorrectly survives authoritative settled states. |
| **Overall** | **10** | **8.70** | **Visual threshold met; independent acceptance remains FAIL.** |

The overview, detail, and approval/output dialogs are visually usable across the observed matrix. Important controls are reachable through normal vertical scrolling; the supplemental 900×650 and 1366×768 images substantiate their actual lower controls rather than grading unseen content. Disabled controls correspond to server authority and captured stale reviews cannot grant a newer scope. The numeric score is subjective, not a benchmark or backend safety assertion.

## Concrete defect

**Medium severity, owner Worker 2, blocking section-17 truthfulness acceptance:** `cancelled-pending-action-900x650-native.png` shows `Cancelled · Assisted · Not started` and a Finished timestamp while the banner still says “Cancellation requested. The backend will stop at a safe execution boundary.” The same contradiction appears at 1440×900 and 1366×768. `revoked-scope-900x650-native.png` shows authoritative Paused and enabled Resume while saying “Pause requested. The backend will stop at a safe execution boundary.” The latter also remains at the larger observed sizes. These are retained request flags after settlement, not an uninterruptible action still returning. Pending copy should be conditional on authoritative unsettled state/active execution; settled pause/cancel should display confirmed state or omit the pending message. Preserve the warning while a real noninterruptible operation remains active. No backend or permission repair is required by this finding.

Representative evidence is in `data/hanni-v3-review/native-cycle-2/`: the two defect frames above, `resolved-action-review-supplemental-900x650-native.png`, `changed-plan-review-supplemental-900x650-native.png`, `verified-read-step-1920x1080-native.png`, `recorded-overview-1366x768-native.png`, `reopened-verified-report-1920x1080-native.png`, `saved-report-output-supplemental-900x650-native.png`, and `results.json`. All raw captures remain unchanged.

## Actual behavior verified

The review exercised real authenticated private HTTP, original WorkflowHub/Service, host, registry, permissions and local file handlers. Captured plan approval from a second authorized window invalidated the first window's old review. Escape/rejection/revocation/cancellation admitted no unapproved original write. Exact resolved action approval produced one real file write. An actual pre-stat error led to explicit safe retry and verified original read. The owned native client closed while a genuine original managed-file invocation was active and noninterruptible; the independently owned attached backend remained running, completed the exact original bytes with verified SHA, and a newly launched real native window displayed the persisted Completed workflow and saved excerpt. This demonstrates the attached-backend lifecycle, not work continuing when Windows is asleep/off or when the backend is terminated.

The executable/frontend/production-runtime/tracked-public-config before/after hash comparisons passed. `results.json` includes exact identities and the complete check list. Ignored provider credentials were neither read nor hashed. Every owned native window/process was closed after review. The underlying fixture/backend was cleaned up.

Disclosed seams: scripted two-pass planning client, inactive synthetic telemetry, one original-stat pre-handler failure, and one bounded original-write barrier for lifecycle timing. No genuine language-model inference, provider, microphone, SSH, power or terminal operation is represented by this native run. The first failed missing-Origin harness cycle is retained separately; the only cycle-2 harness correction added the exact loopback Origin and bounded safe rejection diagnostics, without relaxing any outcome/control assertions.

Next step: checkpoint this failed independent review, repair only the settled-state UI copy, rebuild/freeze, and repeat actual native controls/pixels before the sealed once-only model evaluation. Model evaluation remains unexecuted.

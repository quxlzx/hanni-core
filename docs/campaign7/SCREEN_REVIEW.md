# Campaign 7 screen and UI review

HANNI has no registered screen acquisition, retained screen context or vision
interpretation pipeline in this checkout. The existing Screen awareness page
truthfully reports unavailable capture. Four separate voice UI errors were
reproduced in the shipped application and repaired with narrow frontend freshness
checks. These repairs do not add screen awareness or prove acoustic performance.

## Implementation and evidence boundaries

`DesktopFeatures.awareness()` reports `available=false`, `capture_active=false`,
`enabled=false`, `context_available=false`, `expires_at=null` and all three
actions disabled. An actual isolated default registry contains 172 definitions
and no `screen.*`, `vision.*` or `camera.*` definition. The historical vision
milestones in CLAUDE documentation do not describe the current implementation.
The current configuration contains one model identifier and role, `supervisor`.

The manager observed the existing native endpoint declaring vision and video
modalities for Qwen3.5-4B/Q4_KMedium with context 16384. This is an endpoint
declaration, not successful image inference or a HANNI capture integration.
HANNI's original native controller adapter rejects multimodal message content
before network dispatch. No model was started, downloaded or invoked here.
The manager's available RAM measurement was approximately 1.13 GB at 96.7%
usage, below the unchanged 3072 MiB reserve and above the 90% critical limit.
Additional model loading was therefore not authorized.

The input-only executor is `scripts/campaign7_screen/audit.py:run_case(case,
fresh_root)`. It calls the original isolated configuration parser, feature
projection, registry, HTTP authority gate, native admission guard and React
component. Controlled endpoint rows and synthetic images are labelled as such.
Expected answers are refused at the executor boundary. No original registered
handler is replaced. Expiry, capture and sensitivity operations return explicit
`NOT_IMPLEMENTED` receipts instead of synthetic successful captures.

## Required screen coverage

| Requested scenario | Actual result and limitation | Evidence |
| --- | --- | --- |
| Capture permission | Dashboard authority controls pass: no token or foreign origin returns 403. An authorized capture request returns 404 because no capture route is registered. Capture-specific permission and acquisition remain NOT_IMPLEMENTED. | Original owned HTTP controls; `implementation-cycle3.xml` |
| Actual capture status | Observed disabled: all capture/context flags false, no expiry, all actions false. This is a status check, not a capture pass. | `audit-current/receipts.json`, actual `DesktopFeatures.awareness()` |
| Screen selection where supported | NOT_IMPLEMENTED: no registered window, display or screen selection interface. No physical display was enumerated or captured. | Dynamic registry inventory and source inspection |
| Image acquisition | NOT_IMPLEMENTED: no acquisition path or capture frame was exercised. A headless UI screenshot is separate test evidence. | `audit-current/inventory.json`, zero acquisition scope |
| Vision-model invocation | BLOCKED: original native adapter rejects image/list/dict content before any socket connection; no integrated vision capability is registered. | Three native adapter controls; `audit-current/receipts.json` |
| Image interpretation | NOT_IMPLEMENTED: no captured image, integrated interpreter or actual vision output. Accuracy and capture-to-response latency are null. | Original feature/registry inventory |
| Expired screen context | NOT_IMPLEMENTED: retention is saved metadata only; no retained frame or expiry mechanism exists. Values 1, 30 and 120 are parsed and reported, never treated as expiry enforcement. | Three metadata controls; `expiry-unimplemented` receipt |
| Disabled capture | Observed disabled: analysis remains unavailable in the real React component and shipped browser page, including missing token or resource errors. | Three React controls; `screen-unimplemented.png` |
| Unavailable vision model | Original registry rejects a missing configured identifier with KeyError and zero model dispatch. Controlled eligibility rejects missing verified vision capability, unsupported remote transport, denied privacy or missing context proof. This does not claim that the existing endpoint lacks a declared vision modality. | Missing-model control plus five admission controls |
| Sensitive data handling | NOT_IMPLEMENTED for capture exclusions and image redaction: saved synthetic exclusion configuration adds no pipeline. Native image admission makes no connection in these controls. No personal application, webcam or physical screen was acquired. | `audit-sensitive-corrected/receipt.json`; bounded runner safety controls |
| UI indicators | Four stale/error voice indicators were reproduced independently, repaired and retested. Screen unavailable status already passed. Normal Voice reconnect remains functional in synthetic page tests. | Seven unchanged prospective UI cases and actual PNGs |
| Capture shutdown | NOT_IMPLEMENTED: there is no active capture process to stop. Authorized stop still returns 404, including an already-set shutdown event; owned test HTTP servers and browsers close. This is not proof of capture-stop latency. | Original HTTP shutdown control and closed UI-run receipts |

Paths in this table are under `data/campaign7-screen/` unless otherwise stated.
Unsupported feature rows remain outside the successful vision/acquisition
denominator. The 32 passing implementation controls establish truthful disabled
states and existing guard behavior, not 32 working screen features.

## Original UI failures and repairs

The unchanged seven prospective cases have SHA256
`f8a10cc383134a6859cb544911f6fa1be606aa1819432dd523e0432e4db527eb`.
They execute the original shipped JavaScript/CSS in one owned headless Edge
browser, served over an owned loopback endpoint. Only synthetic API projections
are delivered. Non-owned origins and API mutations are blocked. Physical
desktop acquisition, microphone, camera and model APIs are not used.

| Frozen case | Original | Final development candidate |
| --- | --- | --- |
| screen-unimplemented | PASS | PASS |
| voice-disconnect-cached | FAIL: disconnected Voice resource retained Active/Speaking claims | PASS: current Voice fields unavailable; controls disabled |
| voice-reconnect | PASS | PASS |
| workspace-stale | FAIL: stale sample retained Speaking and microphone amplitude | PASS: unavailable and zero displayed amplitude |
| workspace-sample-error | FAIL: failed sample retained Speaking and amplitude | PASS: unavailable and zero displayed amplitude |
| mini-stale | PASS | PASS |
| mini-sample-error | FAIL: failed sample retained Speaking and amplitude | PASS: unavailable and zero displayed amplitude |

Original evidence: `ui-baseline-cycle1/results.json` and seven PNGs, 3/7 pass.
The independent verifier reproduced 3/7 and reviewed the failed frames in
`data/campaign7-verifier/ui-independent-before/`. Candidate cycles 1 and 2 each
pass the same seven checks; cycle 2 contains the final approved voice copy.
Candidate `ui-candidate-cycle2/results.json` confirms source unchanged throughout
the run, no external-origin or mutation attempts, and owned browser/server closed.
The development engineer viewed the disconnected Voice and stale Workspace
candidate PNGs. Independent candidate acceptance is reported separately by the
verifier; the private final holdout has not been consulted for development.

Production changes are confined to:

- `awareness.tsx`: cached Voice fields require a current successful resource.
- `mini.tsx`: telemetry sample errors invalidate current activity and meter.
- `workspace.tsx`: existing stale/error classification gates current speech,
  processing, microphone detail and amplitude; a separate healthy chat resource
  keeps its own availability semantics.
- Rebuilt original static assets. Layouts, backend behavior, voice controls,
  privacy policy and freshness thresholds retain their existing design.

Voice explanatory copy now describes synthesis or playback activity, and the
Workspace footer says Speech activity. The backend `speaking` flag may become
true during synthesis before audible playback. These labels do not establish
first-audible speech; the independent strict speaking-state failure remains
documented rather than being converted into a successful acoustic test.

## Validation and preserved checkpoints

The pre-repair archive contains 255 source, frontend, shipped-asset and applicable
test files, with no owner databases/configuration. It is retained at
`data/campaign7-screen/original-source/`; archive SHA256:
`7f49f555aa1b324ba00e91d303a54b8aba8aa0b725838dff8f92a9b028ecd7b8`.

Final commands and evidence:

```powershell
# Run from frontend: TypeScript validation and original Vite production build.
npm run build

# Run from the repository: original isolated implementation controls.
.venv\Scripts\python.exe -m pytest tests/integration/test_campaign7_screen_controls.py -q --junitxml=data/campaign7-screen/implementation-cycle3.xml

# Original shipped UI with unchanged prospective checks and actual page frames.
.venv\Scripts\python.exe -m scripts.campaign7_screen.ui --output data/campaign7-screen/ui-candidate-cycle2
```

The final build passes, transforming 67 modules. The final implementation suite
passes 32/32, zero failures/errors/skips (JUnit elapsed 6.260 seconds). The final
UI run passes 7/7. Initial development compiler nullability errors were corrected
without weakening TypeScript. An initial pytest fixture name `request` was
reserved by pytest; its collection failure is retained in
`implementation-cycle1.xml`, followed by the unchanged-assertion 31-case pass in
cycle 2 and the additional prospective missing-model diagnostic in cycle 3.
An initial synthetic exclusion fixture used the unsupported key `processes`;
the original parser's ConfigError is retained in `audit-current/receipts.json`.
The separate corrected fixture uses `process_names` and explicitly reports
NOT_IMPLEMENTED, without regrading the original error.

All owned browser contexts, static servers, HTTP authority fixtures and model
admission engines are closed. No owner voice/model process or configuration was
changed. Observed campaign calls contain no personal screen, webcam, microphone,
speaker or model acquisition; this bounded statement is not a claim about all
installed software or independently running owner activity. Image accuracy,
capture latency, retention enforcement and physical capture shutdown latency
remain null.

Source-ready hashes and scoped evidence identity are published in
`data/campaign7-screen/SOURCE_READY.json`. The manager controls whole-source
freeze and the verifier's once-only independent final execution.

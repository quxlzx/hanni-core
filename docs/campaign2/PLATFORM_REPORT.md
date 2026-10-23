# Campaign 2 platform implementation audit

The dynamically discovered platform subset contains **72 original definitions** across eleven modules. Every definition has a natural-language scenario, valid semantic arguments, original-handler dependency context, unavailable-dependency context, and independent semantic/readback checks. Coverage is compared with the fresh original registry subset; the observed count is not a denominator hardcoded into the coverage assertion.

Ordinary audit case modes are **38 LIVE, 3 ISOLATED, and 31 MOCK**. LIVE covers safe local telemetry and fixed read-only OS queries. ISOLATED covers synthetic environment values and an exact disposable child process. MOCK covers GUI, playback, audio controls, service changes, and power controls. A mocked setter proves the original implementation's behavior over a controlled dependency; it does not prove a change to the user's hardware.

| Original module | Discovered definitions |
| --- | ---: |
| system | 9 |
| windows | 6 |
| apps | 7 |
| media | 9 |
| spotify | 9 |
| net | 6 |
| power | 6 |
| security | 6 |
| devices | 5 |
| uiextra | 4 |
| envtools | 5 |

The fixture interface is implemented in [platform_cases.py](../../scripts/campaign2/platform_cases.py) and [platform_fixtures.py](../../scripts/campaign2/platform_fixtures.py). Registered definitions, handlers, argument validation, permissions, confirmation, emergency stop, and audit remain original. Fixtures terminate at module-scoped psutil access, PowerShell transport, synthetic Win32 DLL calls, or optional pycaw COM interfaces. The original Win32 enumeration callbacks and audio endpoint/session lookup paths execute. Each case also records machine assertions and dependency calls for the manager's receipt ledger.

For `process.stop`, the context creates one owned child, binds only that PID, invokes the original process handler, independently verifies its termination, and closes the exact child in `finally` if it remains alive. No scan-and-kill cleanup is used. Network port readback creates one owned loopback listener and verifies that its actual PID/port appears. Synthetic files and reports remain under each case's isolated directory. No owner process, service, power plan, window, volume, playback, external provider, credential, or production setting was changed.

## Reproduced defects and repairs

Original baseline evidence is retained locally in `data/campaign2-engineering/readback-baseline/results.json`, `missing-battery.json`, and `adjacent.json`. The independent verifier replayed archived commit `e673ccc` and retained its own source-bound baseline in `data/campaign2-verifier/platform-original-a/results.json`. All fifteen archived cases exposed incorrect success or certainty.

| Original defect | Result after repair |
| --- | --- |
| Spotify focus ignored a refused foreground request | Compares the actual foreground HWND with the requested window; reports the request acceptance separately and fails an unobserved focus. |
| Spotify volume reported the requested number after a no-op setter | Returns actual session readback, requested value, and observed change; target mismatch fails. |
| System volume returned success despite observed target mismatch | Compares endpoint readback with the requested absolute or relative target. |
| Audio mute reported the requested boolean after a no-op setter | Reads actual mute state after the setter and fails a mismatch. |
| Brightness claimed a change without readback | Reads brightness before and after the request; unknown or mismatched readback fails. |
| Power plan reported success even though the old plan remained active | Compares actual active GUID with the requested GUID. |
| AC idle timeout reported success without reading settings | Reads the applicable timeout after the request and fails unknown or mismatched values. |
| Window state reported applied state without observing it | Uses original Win32 minimized/maximized getters and reports verified versus matched counts. |
| Minimize-all treated ShowWindow's previous visibility as success | Counts windows observed minimized, rather than interpreting that return value as a success flag. |
| Empty Defender payload meant protection OFF | Missing measurements return unknown and explicit failure. |
| Empty firewall payload meant all profiles enabled | Empty or incomplete profile measurements return unknown and explicit failure. |
| Empty reboot-state payload meant no restart pending | Missing measurements remain unknown; genuine measured pending/nonpending states are retained. |
| Empty disk-health payload meant all disks healthy | Empty or incomplete health inventory fails; genuine known healthy/warning states remain distinct. |
| Missing system battery omitted its promised percentage | Returns unavailable with nullable percentage/charging/time values. |
| Missing detailed battery invented plugged-in state and omitted remaining time | Returns unavailable with complete nullable measurement fields. |

The independent verifier additionally reproduced strings such as `"false"` becoming true through Python truthiness in three security handlers. The final parser accepts actual booleans and native integer enum values 0/1. Unsupported types remain unknown. Twenty-one malformed-value regressions and twelve genuine boolean/enum regressions cover this distinction. Access-denied and provider exceptions are not converted into successful empty inventories.

New Win32 readbacks configure HWND argument and return types to preserve pointer width. Runtime payloads remain compatible or gain explicit requested/observed/verified fields. Six existing output descriptors gain truthful nullable measurement types: `audio.mute`, `system.battery`, `power.battery_detail`, `security.defender`, `security.firewall`, and `security.pending_reboot`. Permissions and argument schemas are unchanged.

## Validation and source identity

Final focused validation on the frozen candidate:

* **270/270 platform checks passed**, `data/campaign2-engineering/platform-repair-final.xml`. These exercise all discovered original platform handlers, unknown-argument rejection, unavailable-dependency branches, nine silent setter failures, empty/incomplete measurements, absent batteries, native boolean types, malformed boolean types, and Win32 previous-visibility behavior.
* **109/109 relevant existing tool/contract checks passed**, `data/campaign2-engineering/platform-legacy-final.xml`.
* The earlier 224-case baseline and initial harness failure remain retained. The one initial harness failure was an omitted `psutil.NoSuchProcess` exception classification; the original owned-helper handler correctly failed when its dependency was unavailable.
* Independent first replay accepted **15/15 repaired original-handler cases** after retaining fifteen archived failures. Final pointer-signature and strict-type acceptance is recorded separately by the verifier, without rewriting its earlier evidence.

The final source manifest is `data/campaign2-engineering/source-freeze.json`, captured at `2026-10-10T06:46:00.901812+00:00`. Baseline hashes below cover Git object bytes from `e673ccc`; candidate hashes cover the physical frozen checkout. The independent archived loader also retains its own exact load hashes, so newline normalization is not mistaken for a behavioral difference.

| Production source | Baseline Git blob SHA256 | Candidate checkout SHA256 |
| --- | --- | --- |
| system.py | `c0c9e495f090e26d56ff0f9647020b19e4abd47ea71bf88f63d2be1ca3ec6aef` | `eb7ab160ea66386da409abf896f96197b3f9cab024a883505b545a385d4b9a60` |
| spotify.py | `9c99b891d4f287673fe64f5c1783e43306d23442697910e857b0fb10e37eb20f` | `d16e014bf0905411d576d55fc8939457c8e8c584c6c2e077e362ac6342667ad6` |
| media.py | `ce4be4f2066c65fd00219d9bfa74581d1a6301c1dfa5354c03f35874c2e36048` | `a5cd71512e2b45debd5c0ae60feca0a687434a2ff660bd6c4b14d9c114806e40` |
| power.py | `7d2f75feda54a493f441f6fa5138817d2161393a2184b66dc82b842966d5169d` | `564ee08ecb99bc13ad40156583dfb479292883c876f614620451be016bae3e83` |
| security.py | `4de75021611c4ff39a4e6345b6c57ad95d28414c1902e5bc40a7f2425248f9ad` | `c50d8dcbb525242499a0de61cb818b533fd2192cd2aba2ada20c2d7d22f5b450` |
| devices.py | `c90cffdfa58a38f2b2513ad69d386dab02d659c1cf6f3f9d2997b69e9286b220` | `a3750d00af070fdfbb143b6189adbddb67e69d652e59476949deef0e55292c03` |
| uiextra.py | `5ecd6851a12b63a7663c99fff6611802798343af97b730130bc6d5e507c686cf` | `66aab22ecaa3e51116c138aa0e3089317897c91853f957ca9e0654a01627041a` |

The manager owns the exhaustive capability scorecard, actual model selection diagnostics, full regression, checkpoints, and final acceptance. This platform report does not turn guarded model refusals, missing optional integrations, or mocked hardware operations into live success claims. No engineering-owned application/model runtime was started for this campaign; every temporary helper and socket was closed by its owning context.

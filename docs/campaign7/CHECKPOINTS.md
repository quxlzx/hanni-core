# Campaign 7 checkpoints

## Cycle 0: original source, inventory and prospective tests

The manager archived 466 original source/config/frontend/asset/test files at
`data/campaign7-manager/preflight/source.zip` before production changes. Source
manifest SHA256 `e974db5bc72ede88fae867a92a184625c27594b4335fc4d42d441a519ba7f902`;
archive SHA256 `3570f8fe36cf3591287816ced91ed12e6e290a6f4933a9fb2889a863efb23a5d`.
Read-only enumeration found 15 input entries (including API aliases), one output
and two installed SAPI voices. No recording, playback, desktop capture, camera
access or model generation was started. Original source stayed byte-identical.
The actual owner service already reported an active microphone; this is a state
observation, not a campaign acoustic validation.

Original memory headroom was 1,131,859,968 bytes free, 96.7 percent used, below
the 3072 MiB configured reserve and above its 90 percent critical threshold.
Additional STT/VAD loading is blocked. Native model metadata declares vision and
video, but the HANNI screen API reports no registered capture/vision pipeline.

The voice engineer sealed 100 newly synthesized WAVs before decoding:
references SHA256 `fda67a89bb2bae99eeb4738e0e086370f6f8d81e67de2aef33b96fb448244ecc`;
manifest SHA256 `136a7ff454fb8ed8e4e068e031341b71f8a3dfe9e47197a6b61a3a283d02446e`.
Actual SAPI synthesis targeted files only. This does not establish STT accuracy
or speaker operation. The verifier separately sealed 60 private cases; public
provenance is `FINAL_SEAL.json`. Private material is never inspected by engineers.

Voice development boundaries originally yielded 14/23 passes, nine failures;
existing focused regressions passed 46/46. Seven proposed causal defects await
independent reproduction. Screen/UI original seven prospective cases yielded
3/7 passes and four failures, with original shipped-asset screenshots retained
under `data/campaign7-screen/ui-baseline-cycle1`. Source was not changed by probes.

## Cycle 1: cancellation, segment continuity and stale UI

The independent original 13 boundary variants reproduced ten failures across
pre-cancelled capture, decoder rate validation, forced utterance segmentation,
pump reuse, failed resume, closed reads and failed-pump availability. Five
voice source files received narrow lifecycle/schema/state repairs. Engineer
focused tests passed 132/132; the independent same 13 variants passed 13/13.
Results are preserved in `data/campaign7-voice/repair-focused.xml` and
`data/campaign7-verifier/development-expanded-after/RESULTS.json`.

The voice candidate source identities were microphone `96d7359f9e6c92843e6ed34e7202ed6b69ffd7c8f5e4006c7f7a5d4e613e4cd2`,
STT `b8e107a5f5b92a0141e993d2bd0245d3cdd925eea35c672824445f8509bbc41c`,
pipeline `367d1d5cb99dee7f4381fecab98cd3b72bf431ae19e471b7e499cb9e7944cfd7`,
pump `9290302f0d97a50de79ae3f3c571b416992193dee77e5b2cfd5b59bb1d03424a`,
dashboard voice `c3c1d42307bdb04b2b28e9729be51c69f030fa75140791c05305f675b61b76ce`.
These are intermediate identities; later repairs have separate receipts.

Three frontend sources received error/freshness gates and shipped assets were
rebuilt with the original build stack. The unchanged seven prospective actual
headless UI cases improved from 3/7 to 7/7, independently reproduced at
`data/campaign7-verifier/ui-independent-after`. Screenshots use synthetic state
and do not validate HANNI screen capture. Screen implementation controls passed
31/31. Initial reserved-pytest-parameter collection failure is retained and
excluded from successful execution denominators.

## Cycle 2: failed actions and honest speech evidence

The independent verifier reproduced a remaining mismatch: an unavailable failed
pump still accepted listen/unmute. These activity-increasing actions now fail
closed; mute/interrupt remain usable to reduce activity. Candidate dashboard
voice identity `9fd233e68b612bd4e942ed92bf8263c18502fd21d235395f07e10668d9ebd563`.

The strict focused suite yielded 146/147 passes and one retained failure at
`data/campaign7-voice/repair-cycle3-strict-focused.xml`. Independent controls
yielded 17/18 passes. The remaining case detects logical TTS preparation marked
Speaking before playback exists. No acoustic success or first-audible timing is
inferred. A temporary verifier xfail collection is archived but is not acceptance
evidence; the expectation was restored and strictly failed. Frontend explanatory
copy is being corrected to describe synthesis/playback activity without claiming
audibility. No core synthesis policy or physical-phase instrumentation is added.

The main agent's broader dashboard/config/safety integration suite passed
165/165 at `data/campaign7-manager/integration.xml`. The single bounded memory
recheck found 1,406,386,176 bytes free and 95.9 percent used: real additional
STT/VAD model loading remains resource-blocked.

## Cycle 3: inactive pipeline privacy

Before the final freeze, independently reproduced completion/cancellation/error
controls found synthetic raw/text/segment data retained after pipeline exit,
past the configured 120 seconds. Original proof is preserved in
`data/campaign7-verifier/pipeline-retention-before.json`; three new expectations
are prospective and separate from the untouched holdout. A narrow finally block
to clear pipeline-owned buffers and reset segment/VAD state is authorized after
this reproduction. Direct process_chunk diagnostics retain their existing API.
Implementation and final verification receipts will be appended after execution.

The final pipeline identity is
`93fe0401c20257fe48a90556ddb341d8acee55751d8b3b8b638b788ca198e5dd`.
Own retention controls improved from 1/7 to 7/7; independent completion,
cancellation and error cases now have empty raw/text buffers and segment
references with one existing VAD reset. The final independent exposed module
reports 32/33 strict passes. The final voice-focused XML accounts for 168/169
passes, listing 166/167 testcase nodes plus two passing subtest accounting
entries. The remaining strict failure is logical synthesis labelled Speaking.

## Cycle 4: source freeze and final independent run

The first 592-file final snapshot had manifest
`9afcdc7fde447086d53f5bcb240eaadeade5e29341596c620db22840180169e7`.
Its precheck caught late scope-description updates in FINAL_ADAPTER.md,
executor.py and publish.py before any private claim or case execution. Snapshot,
aborted precheck and initial main regression artifact are retained. The reviewed
changes did not change predicates, execution rules or private inputs/oracles.

The fresh 592-file snapshot at
`data/campaign7-manager/final-freeze-cycle2` has manifest
`bf81ff201ddeb16f7b9fd281dc7e124190042031308fe3b6c8509630502ceffa`
and archive
`109c881fd79f40d7c26b8b87897d715a43dedc1f86472fbce6128072afccf604`.
The final 60-case private suite ran exactly once on these bytes: 53/60 strict
passes, voice 35/36 and screen 18/24, zero harness errors. All seven misses remain
failed; the independent diagnoses identify one TTS-phase limitation and six
prospective screen-contract conflicts. No final tuning or score promotion occurred.
Oracle-free publication is `FINAL_VERIFICATION.json`.

The main final XML, `data/campaign7-manager/final-integration-cycle2.xml`, accounts
for 361/362 passes with no errors/skips. It lists 341 distinct testcase nodes:
340 pass and one strictly fails, with zero duplicate IDs. Twenty-one additional
passing subtest/accounting entries have no separate node. Suite duration is
29.711 seconds, not model/audio latency. The shipped UI and independent final
copy checks pass 7/7; screen implementation contracts pass 32/32.

The final close check reports zero mismatches across the 592 frozen files,
unchanged protected configuration/audio/compute data, unchanged 121 prior
campaign/owner files, preserved .gitattributes prefix and identical owner process
IDs, creation times and command hashes. Actual model inference, new physical
microphone recording, speaker playback, desktop acquisition and webcam use are
zero. Full hardware/STT/vision metrics remain null. Documentation may be added;
frozen source remains held and changes remain uncommitted.

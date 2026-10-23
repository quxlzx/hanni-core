# Campaign 7: voice and screen awareness

Campaign 7 produced verified implementation repairs and a controlled validation
report, but **full acoustic and visual validation is blocked**. Real STT/VAD
inference could not be admitted under current memory limits; supervised physical
readiness was not confirmed; the configured native Catherine voice is absent;
and HANNI has no registered screen-capture/vision interpretation pipeline.
No software mock, synthesized WAV or browser screenshot is counted as physical
microphone, speaker, wake-word, barge-in or HANNI screen-awareness success.

The final untouched controlled holdout passed **53/60** strictly: voice 35/36,
screen 18/24. Seven misses remain failures. The main frozen regression run passed
**340/341 distinct checks**, with one strict synthesis-state failure. The shipped
UI passed all seven unchanged browser scenarios. These results establish software
contracts and state behavior, not real acoustic or vision accuracy.

Detailed coverage and independent evidence are in [VOICE_REVIEW.md](VOICE_REVIEW.md),
[SCREEN_REVIEW.md](SCREEN_REVIEW.md), [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md)
and [FINAL_VERIFICATION.json](FINAL_VERIFICATION.json). The prospective rules and
durable cycles are [PROTOCOL.md](PROTOCOL.md) and [CHECKPOINTS.md](CHECKPOINTS.md).

## Actual environment and evidence

Windows enumerated 15 input entries, including different API aliases rather than
15 distinct physical microphones, and one SAPI output. The saved choice is the
Realtek microphone at MME index 1 and Realtek speakers. The owner service already
reported an active microphone with a small measured input level. This read-only
observation is not a supervised speech or physical-device pass. Its routing file
and process were preserved; the campaign did not start microphone recording.

Installed SAPI voices are Microsoft David Desktop and Microsoft Zira Desktop.
The actual configured WindowsAustralianTts file-only call failed before starting
a process because its native Australian voice token is absent. The verifier
independently reproduced that result. Configured Catherine, neural fallback and
physical speaker playback remain unverified; David/Zira file synthesis is a
separate working path. No voice pack or dependency was installed.

The cached `small.en` transcription model and audio dependencies exist. At
preflight, only 1,131,859,968 bytes of RAM were free and usage was 96.7 percent.
The single bounded recheck found 1,406,386,176 bytes free and 95.9 percent usage.
Both fail the unchanged 3072 MiB reserve, 90 percent critical threshold and
additional 1 GiB owned speech-model budget. No extra STT/VAD/neural model was
loaded, owner process terminated or resource gate weakened. There were zero
actual ASR/VAD inference calls, so their quality and speed remain unmeasured.

The existing local model server was healthy and declared vision/video support
for Qwen3.5-4B Q4_K Medium with reported context 16384. This is declared metadata,
not demonstrated image interpretation. HANNI's original native adapter rejects
image content before network dispatch. Its awareness API reports unavailable,
capture inactive, context unavailable and all capture/analysis actions disabled.
There is no registered acquisition, selection, expiry or image interpretation
implementation. Cached vision weights and historical plans do not change this.

## Corpus and real outcomes

One hundred genuinely new, prospectively labelled WAVs were generated using
actual Windows System.Speech into campaign-owned files. Ten phrasing categories
have ten samples each. Five conditions have twenty files each: clean, declared
24 dB noise, declared 12 dB noise, low amplitude and internal pause. References
and waveform manifests were frozen before recognition. All are mono PCM16 at
16 kHz, with 365.99375 seconds of aggregate audio and approximately 11.7 MB of
files. These are synthetic test utterances, not recordings of the owner.

The independent verifier checked all 100 hashes, headers, frame counts, sample
content, RMS/peak and half-second zero pads. No clipped samples were found. All
twenty pause files have at least 600 ms of exact zero. It rendered and inspected
real waveforms across all five conditions; the main agent also reviewed the plot.
Exact injected SNR could not be independently reconstructed without precondition
PCM. No acoustic listening or actual ASR decoding was performed. Consequently
the corpus integrity result is 100/100, while transcription accuracy is null.

Separately, the original deterministic classifiers were supplied the frozen
reference texts. They matched 99/100 development expectations. The retained echo
case conflicts with the owner's configured explicit-interruption priority for
the word “no.” Neither references nor owner policy were tuned. This is text-only
classification using the original SpeechConfig defaults, not exhaustive owner
alias coverage or audio wake precision, recall or STT accuracy.

Actual shipped-page pixels were reviewed in an isolated headless browser using
synthetic API projections and an owned loopback server. Personal desktop pages,
microphone and camera were never acquired. UI screenshots validate rendered
indicators, not HANNI screen acquisition or interpretation. The browser and test
servers were closed; no packages were installed.

## Repairs and verification

Every production repair followed an independently reproduced original failure.
The five changed voice source files implement these architectural corrections:

| Failure | Repair | Layer |
| --- | --- | --- |
| A pre-set stop still constructed and entered capture | Check cancellation before constructing the capture backend | Capture lifecycle |
| Non-16-kHz PCM reached a decoder that assumes 16 kHz | Reject unsupported rate before model use, alongside mono validation | Audio schema |
| Forced maximum utterance completion left VAD active and lost later speech | Reset VAD when a duration boundary forces a segment | Segmentation/state |
| Finished-pump restart replayed stale records/terminal | Drain the completed cycle queue before a fresh thread | Queue lifecycle |
| A stopped pump could re-enter its pipeline | Observe its cancellation token before pipeline entry | Cancellation |
| Failed unmute cleared paused state too early | Commit the fresh pump only after successful start; stop a failed candidate | Resume state |
| A closed in-flight read returned an old transcript | Reject closed, paused and superseded reads | Result handling |
| Failed capture still advertised available | Expose a bounded failure flag and disable current availability | Backend/UI state |
| Failed capture still accepted listen/unmute | Deny activity-increasing commands; preserve mute/interrupt safety reductions | Control gate |
| Ended pipelines retained raw/text/segment references past retention | Clear owned buffers and reset segment/VAD state on completion, cancellation or error | Privacy lifecycle |

Pipeline cleanup waits for its owned run to end; it does not claim immediate
cancellation of a decoder already in progress. Direct process_chunk diagnostic
buffer behavior and owner configuration are preserved. This is ended-session
reference cleanup, not a universal proof of memory erasure throughout Python,
third-party models or conversation storage.

Three frontend sources now gate cached Voice fields, Workspace activity/meters
and Mini activity on their relevant error/freshness state. Four original UI
failures became passes; three original positive cases stayed passing. Disconnect,
stale samples and sample errors no longer retain the tested current claims, and
normal reconnect still works in controlled page tests. Explanatory speech copy
now describes synthesis or playback activity. The original layout/backend and
working inactive screen projection were retained. The original frontend build
passed and generated the shipped asset used in the independent final screenshots.

The independent exposed module passes 32/33 strict checks, and the voice-focused
suite reports 168/169. Screen implementation contracts pass 32/32. Main final
JUnit accounting reports 362 checks, passing 361 with one failure and no errors
or skips. It lists 341 distinct testcase nodes: 340 pass and one fails, with no
duplicate IDs. The other 21 passing subtest/accounting entries have no separate
testcase node and are not inflated into additional distinct test identities.
The remaining failure is the same synthesis state issue described below.
The actual shipped UI passes 7/7 prospective checks. Counts from overlapping
suites are not summed into a larger success denominator.

The selected original Silero adapter test requires a real torch import despite
its controlled iterator. It was excluded under the memory guard. Original
segmenter tests and other affected voice contracts ran; no excluded model test
is counted as passed. The 29.711-second combined test duration and 7.781-second
holdout duration are harness wall times, not inference/acoustic latency.

## Untouched final and retained failures

An actual independent verifier sealed 60 new private cases at
2026-10-10T11:36:52Z, before production fixes. Engineers and the manager did not
read private inputs, answers or author code. Input SHA256 is
`ae7b9c345fdc4981b9fe6cf3f30c5dc04d6e74ac5804e213ae433e5cbff839d3`;
oracle SHA256 is
`6e596b247d11e44ef6013d95a7f9ada0a755033cf2bf85fdb34eff241e398022`.
The input-only executor does not receive expected answers. Grading began after
all raw observations closed. No final case was retried or used for tuning.

The first snapshot precheck detected three late scope-description updates and
stopped before any private claim or case execution. That snapshot and regression
artifact were preserved. The reviewed changes only clarify catalog lookup versus
live model identity; test predicates and oracles were unchanged. A fresh source
freeze was then created. The complete final ran exactly once, with zero harness
errors and identical source hashes before/after.

| Final group | Strict result | Meaning |
| --- | --- | --- |
| Voice | 35/36 | Controlled classifier, adapter, pump and state contracts |
| Screen | 18/24 | Existing guards and truthful missing-feature/disabled projections |
| Overall | 53/60 | 88.33 percent controlled predicate agreement; not physical/model quality |

| Retained final miss | Independent cause | Disposition |
| --- | --- | --- |
| C7F-036 | Existing logical TTS preparation sets Speaking before a playback object exists | Remains a strict failure and an architectural phase/observability limitation |
| C7F-038, C7F-050 | Prospective contract expectations conflict with the original validator rejecting out-of-bound saved retention settings before producing status | Remain strict failures; no invalid configuration acceptance was added |
| C7F-051, C7F-052, C7F-057, C7F-058 | Overbroad all-controls-disabled expectations include benign Refresh status; the actual Analyze screen control is disabled | Remain strict failures; no score promotion or unnecessary disabling of Refresh |

The six screen misses do not demonstrate capture or permission bypass. They also
do not establish working capture: that implementation is absent. Final React
projections render ScreenAwarenessPage only; a fixture's surface/profile/image
label does not create execution of a separate screen, account or vision model.
These limits are pinned in [FINAL_ADAPTER.md](FINAL_ADAPTER.md).

Logical Speaking includes synthesis preparation. Current telemetry has no
independently measured audible-start signal, so first-audible stays null and
the strict failed expectation stays failed. Source was not tuned after the final
holdout. A temporary exposed-test xfail artifact is preserved but excluded from
acceptance; the actual final and final combined run use the strict expectation.

## Requested measurements

| Metric | Actual result | Limitation |
| --- | --- | --- |
| Wake-word precision/recall | null / null | No actual audio recognition or supervised wake test |
| Speech transcription accuracy / WER | null / null | Cached model was not loaded or invoked |
| End-of-speech latency | null | No real VAD end signal was measured |
| Time to first audible response | null | No speaker test or audible-start signal |
| Interruption latency | null | Controlled stop dispatch is not physical barge-in latency |
| Vision task accuracy | null | No integrated image interpretation or actual vision invocation |
| Capture-to-response latency | null | No HANNI capture pipeline or captured-model response |
| Observed personal-data privacy violations | 0 | No personal audio/desktop/camera collection, owner writes or unauthorized external dispatch observed |
| Controlled ended-pipeline retention violations | 3/3 before; 0/3 after | Independently tested completion, cancellation and error with synthetic data; no claim of universal memory erasure |

Full coverage rows for all 18 voice scenarios and all 12 screen scenarios are in
the linked specialist reports. Hardware enumeration, fixture device selection,
deterministic wake/stop/echo logic, owned playback cancellation and UI reconnect
have bounded evidence. Real room noise, recognition, audible playback, acoustic
barge-in and automatic device/model recovery do not have a live pass. Screen
selection, acquisition, interpretation, expired context, exclusion enforcement
and capture shutdown remain unimplemented, rather than mocked into success.

## Preservation and reproduction

The baseline was HEAD `0aede831853b6876bc8904838a41f7b2ce8f3967`, including existing
uncommitted Campaign 4–6 work. Current protected configuration, audio routing,
compute deployment/proofs, 121 prior campaign/unrelated-owner files and the owner
process identities were preserved. Original ports 8080 and 8765 still belong to
the same processes, creation times and command hashes. No owner restart, model
swap, installation, webcam enablement or physical screen capture was performed.
Memory/workflow databases were not used as test fixtures. Changes are uncommitted.

The final 592-file source/helper/config/frontend/test/public-corpus snapshot is
`data/campaign7-manager/final-freeze-cycle2/source.zip`. Manifest SHA256:
`bf81ff201ddeb16f7b9fd281dc7e124190042031308fe3b6c8509630502ceffa`;
archive SHA256:
`109c881fd79f40d7c26b8b87897d715a43dedc1f86472fbce6128072afccf604`.
The shipped app.js identity is
`7a972cf36710d96d8659cc3f5f923f06bef7b3d5790c1191d1093c54ab79cca1`.
The final close check records zero source mismatches and preserved owner state.
Public JSON and repaired frontend source get explicit byte-preserving attributes;
the original .gitattributes prefix stays intact.

Development controls can be reproduced from the snapshot using the commands and
XML receipts in the specialist reports. The sealed final is consumed and is not
a tuning/retry target. Preserve its original raw observations and private grades;
use new independently authored cases for future work.

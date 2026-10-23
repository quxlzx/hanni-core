# Campaign 7: voice implementation review

The held implementation repairs stop-before-capture, invalid STT input rates, continuous-speech segmentation, transcript-pump lifecycle, failed voice controls and inactive perception retention. The final engineering XML accounts for **168 passes and one strict failure across 169 checks**; it enumerates **167 testcase nodes**, of which 166 pass and one fails, with two additional passing subtest entries accounted in the suite totals. The independent current collection has **32 passes and the same strict failure across 33 tests**. These collections overlap and must not be summed. The remaining failure is the dashboard describing synthesis preparation as speaking before playback exists. Acoustic accuracy, audible response latency and physical interruption latency remain unmeasured.

This review covers the original voice implementation with controlled dependency leaves, actual Windows speech synthesis into owned files, and the manager's read-only device/configuration inventory. It does not claim a microphone recording, speaker playback, actual STT/VAD inference or automatic device/model reconnection. The private final is verifier-owned and was sealed before repairs; its outcomes are outside this engineering checkpoint. The manager coordinates that final without inspecting its private inputs or oracles.

## Preservation and provenance

Campaigns 4–6, owner configuration, voice routing, independently managed services and the five owner untracked files are preserved. Only these five production files changed:

| Production file | Repair scope | Held SHA256 |
|---|---|---|
| `src/hanni/speech/microphone.py` | Return before constructing or entering capture when cancellation is already set. | `96d7359f9e6c92843e6ed34e7202ed6b69ffd7c8f5e4006c7f7a5d4e613e4cd2` |
| `src/hanni/speech/stt.py` | Require the original 16 kHz mono PCM contract before decoder invocation. | `b8e107a5f5b92a0141e993d2bd0245d3cdd925eea35c672824445f8509bbc41c` |
| `src/hanni/speech/pipeline.py` | Reset VAD after a forced duration boundary; release this owned run's buffers/segmenter/VAD when it finishes, stops or raises. | `93fe0401c20257fe48a90556ddb341d8acee55751d8b3b8b638b788ca198e5dd` |
| `src/hanni/speech/live.py` | Drain a completed pump's stale terminal, retain stopped-token semantics, track failure with a bounded boolean and serialize start. | `9290302f0d97a50de79ae3f3c571b416992193dee77e5b2cfd5b59bb1d03424a` |
| `src/hanni/dashboard/voice.py` | Commit resume only after successful start, discard closed/inactive in-flight records, expose failed availability and reject listen/unmute on a failed pump. | `9fd233e68b612bd4e942ed92bf8263c18502fd21d235395f07e10668d9ebd563` |

Original scoped bytes are in `data/campaign7-voice/original-source/`: 40 source/test files, manifest SHA256 `aebe50c62854688410b9b19831b60f3910a489bafabc5db6fe4f3c3b75ebc432`, ZIP SHA256 `721a95719d2040bea2d3229cdb92380b7f1c31264d855ac3f334abeb24c41b41`. The manager independently archived all 466 original source files; `data/campaign7-manager/preflight/SUMMARY.json` records manifest `e974db5bc72ede88fae867a92a184625c27594b4335fc4d42d441a519ba7f902` and ZIP `3570f8fe36cf3591287816ced91ed12e6e290a6f4933a9fb2889a863efb23a5d`.

Core interaction/speaking policy, CLI behavior, wake/echo/interrupt priority, model configuration and owner audio settings did not change. New source, helper and test files use LF. `VOICE_EVIDENCE.json` provides artifact hashes, exact collected node IDs and retained failure counts; `VOICE_CHECKPOINT.json` pins this implementation checkpoint.

## Actual local inventory and execution eligibility

The manager's inventory observed 15 input aliases, one output, saved MME input 1/Realtek and Realtek speakers. Existing owner `/api/voice` activity was active/available with microphone-active and standby metadata; that existing owner activity is neither a supervised test nor permission to inspect its audio. Installed System.Speech voices are Microsoft David Desktop and Microsoft Zira Desktop. The configured Catherine Australian voice is absent from the original OneCore/SAPI search.

The original configured `windows_australian` backend was exercised **to an owned output file only** by the manager. It returned `TtsError` before starting a process because the Australian voice was unavailable: `data/campaign7-manager/configured-tts-file/RESULTS.json`. Its speaker playback count is zero; neural/SAPI fallback playback was not tested. This demonstrates failure of the requested native Catherine path, not failure of every TTS fallback.

The installed faster-whisper, Silero, Torch, ONNX Runtime, NumPy and sounddevice modules and the existing `small.en` cache were inspected without heavy imports or model loads. `model.bin` is 483,545,366 bytes; its sibling tokenizer/config/vocabulary files exist. `soundcard` is absent, limiting original desktop-loopback capture. Cached weights do not establish runtime availability or recognition accuracy.

The original owner reserve remains 3,072 MiB and critical RAM threshold 90%. The manager's initial preflight had 1,131,859,968 free bytes at 96.7% used; its later bounded recheck had 1,406,386,176 free bytes at 95.9% used. Both fail the required reserve plus a 1 GiB owned model budget and the critical percentage guard. **Additional STT/VAD model loading was not allowed.** No owner model was unloaded or guard weakened. Real decoder/VAD model calls, acoustic captures and speaker playbacks in this engineering campaign are zero.

The original effective audio configuration remains 16 kHz mono, 512-sample blocks, VAD threshold 0.5, 500 ms silence, 100 ms pad, 250 ms preroll and 30-second maximum utterance. STT remains `small.en`/CPU/int8/English/beam 1. TTS remains `windows_australian`/Catherine/rate 1/volume 100/120-second timeout/speed 1.06. Root observed six owner wake aliases. The separate reference classifier sweep uses the original `SpeechConfig()` defaults recorded in its receipt, including five default wake aliases; it is not a claim that every owner-configured alias was acoustically tested.

## Prospective development audio and classifier evidence

`evals/voice/campaign7-development/` contains **100 actual locally synthesized WAV files**, 16 kHz mono PCM16, generated with Windows System.Speech output directed to files before synthesis. There was no speaker output. References were written before generation or classification. David/Zira alternate across the files; no file claims Catherine.

There are ten prospective categories with ten samples each: direct wake, wake position, idle background, near wake, engaged follow-up, filler, disengage, passive acknowledgement, playback interruption and playback echo. Five conditions have 20 files each: clean, seeded 24 dB noise, seeded 12 dB noise, low amplitude and a 650 ms internal pause. Rates vary from -1 to 2; seed is `71000 + index`. Every file includes 0.5 seconds of leading and trailing silence. Samples span 1.995–6.025 seconds and total 365.99375 seconds/11,716,200 file bytes. All waveforms contain nonzero PCM. One acknowledgement pair normalizes to the same text; these are 100 annotated audio samples, not 100 distinct normalized requests.

Reference SHA256: `fda67a89bb2bae99eeb4738e0e086370f6f8d81e67de2aef33b96fb448244ecc`. Manifest SHA256: `136a7ff454fb8ed8e4e068e031341b71f8a3dfe9e47197a6b61a3a283d02446e`. The manifest records actual voice, rate, seed, sample format, frames/duration, peak/RMS, original synthesis hash and final conditioned waveform hash. `data/campaign7-voice/CORPUS_FREEZE.json` records the freeze. Independent `data/campaign7-verifier/audio-independent-audit-corrected/RESULTS.json` passes all 100 integrity/header/frame/declared RMS/peak/nonempty PCM/padding checks, observes zero clipped samples and verifies all 20 pause files have at least 600 ms of exact zero PCM. Its SVG/rendered waveform artifact was inspected without audio listening. Exact noise SNR cannot be independently reconstructed without precondition PCM. These facts establish file synthesis and waveform integrity; STT decoding of these files was not run.

Original relevance/barge-in classifiers were separately evaluated against the prospective reference **text**. The retained receipt `data/campaign7-voice/reference-classifiers-before.json` is **99/100**: all 80 non-playback relevance/wake cases pass, and 19/20 playback/barge cases pass. Text-only wake counts are TP 22, FP 0, FN 0, TN 58; these are not acoustic wake metrics. The one failed reference, `c7-dev-playback_echo-07`, contains “no”; the original explicit interrupt priority wins over its echo expectation. That is a conflict between the prospective intent annotation and the intentional configured interrupt phrase priority. Neither the reference nor the policy was changed to erase the failure.

## Reproduced faults and bounded repairs

| Original failure | Before-repair evidence | Repaired behavior and preservation control |
|---|---|---|
| Already-cancelled microphone and desktop sources enter capture. | Own development boundary receipt; independent 256/1024-sample controls. | No backend construction/entry or desktop dependency import after a pre-set stop; healthy capture still enters and closes. |
| Non-16 kHz mono reaches a decoder despite the original adapter contract. | Own 8,000/22,050/44,100 Hz cases; independent 11,025/44,100 Hz cases. | Typed `SttError` before decoding; compatible 16 kHz input and silence behavior retained. |
| A forced maximum-duration segment leaves VAD active and loses subsequent continuous speech. | Own short deterministic cutoff; independent 500-sample/.0625-second cutoff. | Rearm VAD at forced boundaries; prospective 1,876 controlled PCM blocks create two 30–30.033-second bounded segments. This is segmentation, not long-command recognition. |
| A naturally finished pump restart immediately exposes the old terminal. | Own/independent finished restart cases. | Dead-pump restart drains stale queued events; active start remains idempotent. |
| Starting a stopped pump enters a pipeline with a cancelled token. | Own/independent pre-stopped pump cases. | Owned thread can complete compatibly, but pipeline entry is zero; no cancellation token is cleared. |
| Failed managed start clears paused state; a closed in-flight get returns an old transcript. | Own failed start/closed-get and independent pending-get controls. | Only commit resume after a successful fresh start; keep muted state after failure and discard stale records. |
| A failed original pump remains available and accepts listen/unmute. | Independent failed-pump and corrected UUID lifecycle-action evidence. | Bounded safe failure reason and disabled snapshot; listen/unmute rejected. Mute/interrupt safety controls still succeed. |
| Completed/cancelled/failed owned pipeline retains raw/text buffers and active/recent segment state after the nominal retention interval. | Own `retention-inactive-before.json`; independent `pipeline-retention-before.json`, tested at 180 seconds. | `run` finally releases its own raw/transcript buffers, segmenter and existing VAD state. Independent complete/cancel/error readback has zero raw/text, inactive segment, zero recent chunks and one VAD reset. Direct diagnostic `process_chunk` retention and older injected VAD compatibility remain covered. |

The cleanup does not erase copies already yielded to a consumer or assert physical memory zeroing. It runs when the owned generator finishes, closes or raises, not while a decoder is still executing. A controlled blocked decoder demonstrates that mute remains `muting` until it exits and prevents overlapping reconnect. Instant cancellation of synchronous decoding is not implemented. Automatic device/model reconnect and generational cancellation of synchronous assistant generation remain limitations.

## Required voice scenario coverage

| Requested scenario | Outcome and evidence | Live eligibility and practical limit |
|---|---|---|
| Microphone enumeration | Manager's original read-only device inventory sees 15 input aliases/one output; original enumeration unit contracts pass. | Actual enumeration, no microphone stream or recording. Aliases are not asserted to be 15 distinct physical microphones. |
| Microphone selection | Original input selection/persistence tests use disposable state and controlled devices; saved owner selection is observed read-only. | Selected hardware was not opened; physical routing and sample quality are unverified. |
| Wake-word detection | 80 eligible reference-text cases have TP22/FP0/FN0/TN58; original classifier and attention tests pass. | TEXT_ONLY; no WAV recognition or microphone wake precision/recall. |
| Non-wake-word rejection | Reference background/near-wake/filler/acknowledgement controls and native attention routing reject irrelevant text. | TEXT_ONLY; acoustic background rejection unmeasured. |
| Speech-to-text accuracy | Original adapter format, silence, decoder-error and known-return contracts pass with controlled decoder leaves. | Actual `small.en` decoding of the 100 WAVs is resource-blocked; WER/transcription accuracy null. |
| Silence and noise handling | Actual WAV silence/noise/amplitude variants exist; digital zero PCM avoids decoder calls in original adapter guards. | No real VAD or noisy-ASR measurement; nonzero noise does not have an acoustic correctness score. |
| Short commands | Prospectively annotated short utterance files and original reference routing are covered. | Actual short-command recognition not run. |
| Long commands | Original 30-second segmentation is tested with 1,876 controlled PCM blocks and two bounded output segments. | Development WAVs last at most 6.025 seconds; no recognized 30-second command or long-ASR accuracy claim. |
| Multi-turn conversations | Original attentive bridge exercises six controlled transcript turns; exactly two model-session leaves are called and disengagement/background behavior is preserved. | Original text/state integration with controlled session outputs, not live spoken dialogue or real model quality. |
| Assistant text-to-speech | Actual System.Speech synthesis creates 100 owned David/Zira WAVs. Manager's original configured Catherine to-file path fails explicitly before process start. | Actual file synthesis; configured Catherine unavailable. Fallback and audible playback are untested. |
| Speaking state | Controlled playback/failure metadata contracts pass. One strict prospective test fails because original synthesis preparation is labelled speaking before playback. | Partial: logical TTS task activity is not observed audibility. Core speaking policy is unchanged. |
| Voice interruption | Original controlled playback handle receives termination for interrupt cases, including safety commands. | Owned fake subprocess leaf; no audible interruption latency or physical speaker stop proof. |
| Barge-in | 19/20 prospective playback-reference classifications pass; controlled original classifier-to-playback stop path and echo priority controls run. | TEXT_ONLY/state-level; acoustic echo rejection and real speech-over-playback detection unmeasured. |
| Stop command behavior | Pre-set stop prevents capture/desktop/pipeline entry; in-flight closed transcript is discarded; text stop priority preserved. | Controlled lifecycle proof. Synchronous decoder cancellation waits for return and is disclosed. |
| Device disconnection | Controlled capture failure propagates, marks the pump failed/unavailable and denies activity-increasing actions. | No physical device was unplugged; automatic device recovery is unsupported here. |
| Model timeout | Controlled decoder `TimeoutError` becomes typed `SttError` and never a successful transcript; subsequent independent utterance processing is covered. | Dependency fault contract only; no actual model timeout deadline/latency measurement. |
| Backend reconnect | Explicit finished-pump restart and fresh managed resume work; failure retains muted state and closes the new owned candidate. | Controlled explicit lifecycle. Automatic reconnect and live backend recovery are not claimed. |
| Voice-state accuracy in HANNI OS | Native controller snapshots cover unbound, muted, failed, active and closed states; safe failure reason and action gates are checked. | Software/API state, not physical microphone/audibility. Speaking-preparation limitation remains; frontend rendering belongs to worker 2. |

## Requested metrics and causal limits

| Requested metric | Acoustic/actual-model value | Separate eligible evidence |
|---|---|---|
| Wake-word precision/recall | `null`: no actual decoded or microphone signal. | Reference-text TP22/FP0/FN0/TN58 only; precision/recall 1.0 for that text subset. |
| Speech transcription accuracy | `null`: STT model run is resource-blocked. | Format/error/silence adapter controls are implementation contracts, not accuracy. |
| End-of-speech latency | `null`: no real VAD endpoint signal. | Controlled segment timestamps/30-second cutoff do not establish neural endpoint latency. |
| Time to first audible response | `null`: speaker playback never observed. | Original controller's `first_audible_ms` remains null; synthesis-file duration is not an audible response measurement. |
| Interruption latency | `null`: no physical barge/stop signal or acoustic playback. | Controlled owned playback termination proves a state action only. |
| Vision task accuracy | `null` in this voice review; screen evidence is worker 2/root-owned. | No voice-to-vision substitution. |
| Capture-to-response latency | `null`: no supervised capture/model response. | Original `wake_to_listening_ms` test uses controlled transcript timestamps and is not acoustic wake latency. |
| Privacy violations | No campaign physical capture, speaker playback or owner private audio/record access was performed; global violation rate is `null`. | Original pre-stopped capture-entry and inactive-retention boundary failures were exposed and repaired. Current controlled disposal checks pass; yielded consumer copies and owner activity are outside that proof. |

## Retained verification cycles and reproduction

All counts below are read from the named XML or JSON receipt. Every failing receipt remains immutable, including the temporary xfail-marked artifact, corrected fixtures and the final strict speaking failure. These are repeated/overlapping development collections rather than disjoint samples.

| Receipt under `data/campaign7-voice/` | Collected result | Interpretation |
|---|---|---|
| `original-state-regressions.xml` | 46/46 pass, 1.443 s | Original lightweight state baseline. |
| `development-boundaries-before.xml` | 14 pass/9 fail, 23 total, 0.373 s | Original prospective fault evidence before repairs. |
| `repair-focused.xml` | 132/132 pass, 1.877 s | Own23 + independent13 + original96 after initial repairs. |
| `supplemental-scenarios.xml` | 10/10 pass | Additional requested implementation scenarios; no actual ASR/hardware. |
| `repair-cycle2-focused.xml` | 146 pass/one xfail, 147 total, 2.893 s | A verifier's temporary xfail was present at collection; this is not a strict repair success. |
| `repair-cycle3-strict-focused.xml` | 146 pass/one strict fail, 147 total, 2.992 s, exit 1 | Strict original prospective synthesis expectation restored; known limitation retained. |
| `retention-controls-before.xml` | One pass/six fail, seven total, 0.177 s | Inactive-retention baseline before final cleanup. |
| `repair-cycle4-final-focused.xml` | **168 pass/one strict fail, 169 total, 2.906 s, exit 1** | Held current source: own40 + original96 + independent33; one known speaking limitation. |

Independent `data/campaign7-verifier/independent-final-source.xml` is **32 pass/one strict fail, 33 total, 0.380 s**, and `SOURCE_READY.json` pins current source and public measurement helpers. Those 33 tests include voice boundaries and public wrapper/scoring controls, including two screen-wrapper checks; they are not 33 acoustic tests. Independent lifecycle readback is in `lifecycle-actions-after.json`.

The exact lightweight original selection below accounts for 96 checks in the final XML: 94 listed testcase nodes and two additional passing subtest entries. The final combined 169 suite total is 40 own new controls, 33 independent public controls and those 96 original checks; deduplication uses the 167 listed node IDs rather than assuming every suite-accounted check has its own node. In particular, select only `UtteranceSegmenterTests` from the VAD module: the omitted Silero adapter class imports actual Torch even with a fake iterator. TTS tests use fake providers/processes; no neural model loads occur.

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -q tests/unit/test_microphone.py tests/unit/test_speech_buffer.py tests/unit/test_speech_pipeline.py tests/unit/test_stt.py tests/unit/test_tts.py tests/unit/test_barge_in.py tests/unit/test_audio_devices.py tests/unit/test_desktop_voice.py tests/unit/test_desktop_audio_capture.py tests/safety/test_speech_privacy.py tests/unit/test_attention.py tests/unit/test_relevance.py tests/unit/test_live_pump.py tests/unit/test_neural_tts.py tests/unit/test_australian_tts.py tests/unit/test_vad_segmenter.py::UtteranceSegmenterTests
```

The final engineering command adds `tests/integration/test_campaign7_voice_boundaries.py`, `test_campaign7_voice_scenarios.py`, `test_campaign7_voice_retention.py` and the verifier-owned `test_campaign7_verification.py`, with `--junitxml=data/campaign7-voice/repair-cycle4-final-focused.xml`. Its actual exit is 1 because of the retained strict speaking failure; it is not advertised as an all-pass command.

The private final seal remains documented separately in `FINAL_SEAL.json`. Do not interpret this development checkpoint as that final's outcome, a live spoken interaction pass or evidence that hardware authorization was received.

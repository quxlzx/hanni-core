# HANNI's local signature voice

The default is now `windows_australian`, selecting an installed female en-AU
voice, preferring Microsoft Catherine. It speaks locally with a higher pitch.
This is a different voice from the Kokoro blend, not an accent transformation
of that blend. No person's recording is used.

Install **English (Australia)** in **Windows Settings > Time & language >
Speech > Manage voices > Add voices**. Windows manages the download and may
require administrator approval. HANNI reads installed voice tokens without
editing the registry. It checks for the Australian pack at each reply.

If the pack is missing, HANNI explicitly warns and uses the higher-pitched
British Kokoro blend: 65% `af_heart`, 20% `bf_emma`, 15% `af_bella`. It does not
label British speech as Australian. `hanni tts-info` reports whether an
Australian voice is actually installed.

## Start using it

The higher pitch and Australian preference are configured. The Australian
voice requires the Windows pack above. Stop the current HANNI session with
Ctrl+C (answer Y if Windows asks), then run:

```powershell
.\scripts\start_dashboard.ps1 -SkipInstall
```

For a new checkout, or to repair the voice installation:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[voice]"
.\.venv\Scripts\python.exe scripts\setup_hanni_voice.py --play
```

Setup generates `data/voice/hanni-preview.wav` with the Australian voice when
installed. Otherwise it clearly labels the preview as British, prepares the
Kokoro fallback (approximately 354 MB of assets with pinned SHA-256 checks),
and raises its pitch. `--play` also plays the preview. It never installs Windows
language packs itself. Install the optional `voice` extra with the command above.
No API key or cloud speech account is needed. Setup uses the configured data
directory (`HANNI_DATA_DIR` when set); `speech.tts.model_dir` is relative to it,
unless an absolute directory is supplied.

Test a live reply without loading an LLM:

```powershell
.\.venv\Scripts\python.exe -m hanni.cli speak "Hi, I'm Hanni. What would you like to do today?"
.\.venv\Scripts\python.exe -m hanni.cli tts-info
```

## Adjust the voice

In `config/hanni.yaml`, under `speech.tts`, `pitch_semitones: 2.0` raises the
voice. Use `0.0` for original pitch or increase up to `4.0`. Kokoro uses a
semitone resampling ratio and compensates synthesis speed to approximately
preserve pace; Windows uses rounded native pitch steps, whose exact amount
depends on the voice. Both paths support `volume` (0–100). Windows uses `rate`
(-10–10); Kokoro uses `speed` (0.5–2.0). Restart after editing configuration.

To keep the neural blend, set `backend: kokoro`, `voice: hanni`, and
`language: en-gb` (or `en-us`). Kokoro itself has no Australian voice. The
`windows_australian` backend always selects a female Australian voice by its
installed language metadata, preferring Catherine.

To restore the Windows voice, set both:

```yaml
backend: windows_sapi
voice: default
```

With `sapi_fallback: true`, a missing Australian pack falls back to Kokoro;
missing Kokoro packages/assets then fall back to the default Windows voice.
Each missing prerequisite produces a warning. Set the option to `false` to
report an error instead. Errors during synthesis or playback are reported;
they do not automatically replay a possibly partially spoken response.

## Runtime and privacy

Both backends leave GPU allocations unchanged. A hidden process handles each
reply, plays bounded chunks, and exits after the reply. Kokoro also releases
its model memory then. Normal speech stays in memory. There is no speech
server, listening port, runtime download, or stored conversational audio. The
fixed synthetic preview is the only WAV deliberately saved by setup; `data/`
and audio/model files are excluded from Git and source exports.

The existing playback interface still handles barge-in, foreground priority,
completion announcements and the dashboard orb. Stopping playback terminates
the same process doing synthesis and audio, including before audio begins.
An independent deadline prevents stalled neural synthesis from remaining
active forever. The orb follows worker activity, including the short synthesis
phase; its pulse is an animation, not a measured output waveform.

On the current Ryzen 7 7800X3D, the full precision CPU model generated short
replies in approximately 0.7 seconds after loading, with about 490 MB resident
memory. A 5.2-second preview took 2.1 seconds including load. Performance varies
with reply length and system load. The int8 export was substantially slower
on this PC and is not selected.

## Upstream components

- [Kokoro-82M model](https://huggingface.co/hexgrad/Kokoro-82M)
- [Stock voice descriptions and language limits](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)
- [Kokoro ONNX runtime and blending example](https://github.com/thewh1teagle/kokoro-onnx/blob/main/examples/with_blending.py)
- [Pinned model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1)
- [Microsoft's supported languages and voices](https://support.microsoft.com/en-au/windows/appendix-a-supported-languages-and-voices-4486e345-7730-53da-fcfe-55cc64300f01)
- [SAPI pitch controls](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee431815(v=vs.85))

Model assets and optional third-party packages retain their upstream licenses;
they are downloaded during setup and are not bundled in HANNI's source export.

## Validation

- Current full suite: 739 tests and 30 subtests passed.
- The higher-pitch update adds frequency-shift, pace compensation, missing-pack
  fallback, newly installed pack detection and XML/text transport checks.
- Higher-pitched preview synthesis and speaker playback succeeded.
- Native Windows synthesis and pitch markup were exercised using installed
  Zira as a test voice. Catherine's accent cannot be auditioned until the
  Australian pack is installed; Zira is not presented as an Australian voice.
- Cancelling a live neural worker stopped it and cleared the dashboard speaking
  state; unit tests also cover cancellation during stalled synthesis, timeouts,
  fallback selection, stdin transport and private error handling.
- Dashboard browser smoke passed, including orb rotation/pulse, pause, mobile
  layout and disconnect behavior, with no JavaScript errors.
- One-command voice setup, dependency consistency, package build and
  distribution-content checks passed. No repository was published or pushed.

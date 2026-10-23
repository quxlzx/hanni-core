# Milestone 2.4 independent final review

**PARTIAL: accurate unavailable runtime/interface verified; live acoustic tests and measurements pending.** Voice **8.7**, final Mini **8.7**, AI-template **1.2**. Final [cycle3 report](phase-2-cycle-3.md) records actual15/15 Mini checks and every inspected state frame.

Real unbound VoiceControl reports microphone inactive/input zero with disabled Listen/Mute/Interrupt. Full Voice and Mini accurately show unavailable/unmeasured state, device selectors, stop controls and timings; no synthetic microphone activity is presented as real. Mini readiness now starts clean in all four fresh native sizes. Recorded audio regression results remain coordinator-owned.

Required actual wake, listening transition, transcription, assistant response, TTS, barge-in, interruption, return-to-standby and acoustic latency tests were not executed here. Read-only device enumeration and injected state tests are not live voice proof. Wake metric is utterance-end to wake decision, not acoustic wake onset; first-audible response remains unmeasured without a sensor. A coordinated user-spoken-input session and truthful measurements are still required before full acceptance.

Checkpoint source: original-session adapter `4b046d0`, compact Voice `cbcf871`,
Mini readiness `fb6b3cb`. Modified groups: Voice sections in `awareness.tsx/css`,
Mini, `dashboard/voice.py`, narrow CLI observation binding and original-pipeline
regressions. Coordinator's final Python suite passed860 tests,2 skipped,17subtests;
no live acoustic claim follows. Resume with user-spoken input in the original
attentive session, and measure actual audible onset/interruption without replacing
the capture, wake or playback owners.

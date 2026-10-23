# Milestone 2.4 independent review, cycle 2

**Full Voice unavailable-state visual review PASS; actual acoustic feature PARTIAL; Mini startup FAIL.** User-weight Voice **8.7**, Mini **8.3 FAIL**, AI-template **1.2**. Details and actual failed frames in [phase-2-cycle-2.md](phase-2-cycle-2.md).

Full Voice keeps disabled runtime state, devices and measured/not-measured timings together at 1366 x 768. Actual unbound VoiceControl has microphone inactive/input zero; Listen/Mute/Interrupt remain disabled in full page and Mini. Four initial Mini sizes retain raw get_state-not-a-function error despite later native API becoming callable. This is a real readiness defect, separate from voice availability; fourteen subsequent Mini focus/pin/transport/security checks pass.

No actual spoken wake, capture/mute resumption, audible playback/barge-in, desktop-loopback input or latency threshold is exercised. Read-only device/dependency enumeration and injected state tests are not acoustic proof. No first-audible sensor exists; the wake metric is utterance-end to wake decision, not acoustic onset. Evidence: `phase2-primary-cycle2/voice-*-native.png`, `phase2-mini-cycle2/mini-idle-*-native.png`, discovery/conflict/offline frames and existing functional results.

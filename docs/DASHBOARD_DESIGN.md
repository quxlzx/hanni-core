# Dashboard presentation

The main desktop workspace puts measured system vitals, the voice orb, and
conversation alongside one another. At narrower widths the orb and chat come
first, followed by hardware details. Model information, GPU readings, safety,
network activity, jobs, and the supplied benchmark remain available below.

The interface uses local fonts, a navy/cyan palette, consistent panel framing,
readable message bubbles, and a persistent navigation bar. No remote font,
image, analytics, or UI dependency was added. The orb remains drawn locally
on canvas with its existing microphone and playback observers. Speech reaction
is a visual pulse driven by playback, not a claimed synthesized-audio waveform.

Calendar and time suggestion buttons prepare an editable draft; the owner still
uses Send or Enter to submit it. They do not overwrite an existing draft.
Chat messages still render as text, and all existing confirmation, history,
voice, and tool behavior stays in the application layer.

Keyboard users can skip to chat and see focus indicators. System reduced-motion
preferences pause the orb on arrival; Resume motion remains available. Unknown,
disconnected, and Safe Mode states are labeled rather than displayed as healthy.

Validation: 34 dashboard/chat unit tests passed. The Edge browser smoke test
checked text submission, history/reload/clear, suggestion drafts, Shift+Enter,
orb rotation/pause/playback, reduced motion, telemetry, jobs, safe text rendering,
and disconnected state without JavaScript errors. Layout widths checked were
320, 390, 768, 1024, 1280, 1440, and 1920 pixels. Browser assistant replies were
explicit test fixtures; hardware telemetry was real.

Refresh the running dashboard with Ctrl+F5 to load the updated static assets.

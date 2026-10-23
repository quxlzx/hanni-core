# Independent packaged desktop lifecycle and security check

Checked 2026-10-09 by Agent 3 using the actual
`dist/HANNI OS/HANNI OS.exe`. **PASS**, nine recorded checks, no remaining
defects in this scope. Evidence: `data/hanni-desktop-review/lifecycle/results.json`
and actual Win32 screenshots `maximized-native.png`, `resized-native.png`,
`tray-menu-native.png`, and `tray-owner-native.png`, all opened and inspected.

The final executable was rechecked after the owned-startup cancellation fix:
`data/hanni-desktop-review/lifecycle-final/results.json` again reports all nine
checks PASS, zero defects, at120DPI. Its maximized/resized/tray frames were opened
and inspected. This run uses the exact D33B9CB2-prefixed executable hash recorded
in iteration-2.md.

This check attaches only to an isolated synthetic ReviewFixture. It never starts
voice/models, opens an SSH terminal, executes remote power commands, attaches to
production HANNI, or shuts down an externally managed backend. Native interaction
uses actual packaged window handles and Windows popup menu item bounds. The
script is `scripts/desktop_review/check_lifecycle.py`; fixtures/settings/actions
are explicitly synthetic.

## Observed checks

- The packaged WinForms/WebView2 window connects to the existing loopback API.
- A write from the actual WebView without `X-Hanni-Token` returns **403** and
  invokes no fake machine-action handler.
- The WebView exposes **no privileged Javascript native API methods**.
- Foreign-loopback popup and direct navigation attempts leave the current URL
  unchanged, create no additional WebView page, and cause **zero HTTP requests**
  at the independent untrusted test server.
- Maximize, normal minimize, and restore change actual Windows window state.
- Default close exits the desktop cleanly; the attached backend remains ready,
  its workspace API responds, and its shutdown event remains unset.
- A resized **1280 x 800** window at physical position **100,100** restores
  exactly to rectangle **100,100,1380,900** on packaged-executable restart.
  This was tested at the actual **125%, 120 DPI** system scaling. Saved logical
  coordinates/dimensions map correctly to physical geometry.
- The actual native tray menu toggles Close to tray and Minimize to tray,
  persists both preferences, hides the window on the corresponding action, and
  restores it through the tray's default Open HANNI OS action.
- Tray Exit desktop exits even when close-to-tray is enabled, with the attached
  backend still alive and no machine action or shutdown request.

The native menu provides Open HANNI OS, Start Assistant, Close to tray, Minimize
to tray, Desktop notifications, and Exit desktop. Start Assistant was deliberately
not invoked: this check must not start a model or microphone. Optional native
notification delivery was not toggled or claimed as visually inspected.

## Defect and retest history

The first native navigation/popup test found that foreign requests could reach
the untrusted local server even though the visible HANNI page remained in place.
Worker 1 removed the stock popup navigation handler and added a narrowly scoped
native WebResourceRequested same-origin guard. The independent retest then
observed zero popup/direct-navigation requests. This is the actual inspected
result, not acceptance of a source-only claim.

Two verification harness issues were corrected without modifying application
behavior: cached Playwright page URLs require protocol pumping during startup
polling, and keyboard selection of a native tray menu was replaced with mouse
clicks on actual menu-item rectangles. Initial occluded or virtualized images
are not final review evidence.

The dark native application menu and caption now match the application; standard
Windows controls and the `h.` icon remain visible. This document establishes
native lifecycle/security behavior, not the separate five-screen visual score
or final backend/real-telemetry regression acceptance.

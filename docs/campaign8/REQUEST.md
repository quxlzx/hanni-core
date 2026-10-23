# CAMPAIGN 8 — HANNI OS DESKTOP QUALITY ASSURANCE

Apply the common HANNI Validation Campaign instructions.

Launch the actual Windows HANNI OS desktop application.

Do not validate only a browser preview.

Test every implemented screen, control, layout, and frontend/backend interaction.

## Functional coverage

Inventory every interactive component.

Test:

- Navigation.
- Conversations.
- Streaming responses.
- Model selection.
- Agent activity.
- Workflows.
- Memory Explorer.
- MCP Hub.
- Cluster.
- Model Lab.
- Calendar and tasks.
- Notifications.
- Voice controls.
- Settings.
- HANNI Mini.
- System tray.
- Startup/shutdown.
- Reconnection.
- Keyboard shortcuts.

Do not assume every named screen exists.

Test what the actual application provides.

## Visual evaluation

Capture screenshots at multiple desktop sizes and Windows scaling levels.

Inspect:

- Typography.
- Alignment.
- Spacing.
- Information density.
- Visual hierarchy.
- Tables.
- Graphs.
- Navigation.
- Empty states.
- Error states.
- Dialogs.
- Text clipping.
- Keyboard focus.
- Accessibility.
- Consistent design language.

## Typography

Evaluate the currently selected font and at least five alternative suitable font systems if typography quality remains below the required threshold.

Do not change fonts without comparative screenshots.

The verifier independently scores visual and typography quality out of 10.

## Acceptance

- Overall design above 8.5/10.
- Each primary screen at least 8.6/10.
- AI-template appearance 2/10 or lower.
- No critical layout defects.
- No fake telemetry.
- No nonfunctional primary controls.
- No critical accessibility violations.

These are subjective design thresholds and must be backed by screenshots and concrete observations.

## Real function verification

For every major screen, verify the UI talks to the actual backend.

Example:

If Cluster says a machine is offline, compare that status with the authoritative cluster manager.

If a workflow says completed, confirm its persisted result.

If a model says loaded, verify its endpoint and model identity.

The verifier must reject misleading displays even when the layout looks good.

Produce a complete desktop QA report with screenshots and defect references.

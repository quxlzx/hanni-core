---
name: google-calendar
description: Check Google Calendar agendas and availability, prepare meetings, and perform explicitly requested event changes using verified event IDs.
metadata:
  hanni:
    triggers: [google calendar, my calendar, work calendar, school calendar, calendar tomorrow, calendar today, calendar this week, next meeting, reschedule my meeting]
---

# Google Calendar assistance

Resolve dates against the current local time and configured calendar timezone.
Use the selected or default connected account and calendar consistently. Inspect
available tool schemas before supplying dates, intervals or event-change fields.

Use `google.calendar.events`, `.next`, `.list_calendars` or `.availability` for
reads. Availability needs a resolved instant or interval. An empty, complete
result supports "no events in this window"; a partial or failed query does not.
Availability covers only the calendars checked, not every participant's schedule.
Keep all-day dates distinct from timed events and show the timezone for proposals.

For an explicitly requested event, use `google.calendar.create` with the resolved
title, date and duration. Use the returned ID with `google.calendar.read` to
verify the saved event when available. For updates or deletion, identify the
exact existing event and apply the tool's confirmation requirements. Preserve
fields the user did not ask to change; never fabricate an event ID.

The current creation schema does not support attendees, invitations or recurring
event rules. Explain those limits instead of claiming people were invited. Report
the account, calendar, actual saved time and receipt; distinguish creation from
successful readback. If a write has an unknown outcome, inspect before retrying.

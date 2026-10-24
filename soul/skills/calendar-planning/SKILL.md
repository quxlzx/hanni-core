---
name: calendar-planning
description: Prepare meeting agendas, compare scheduling availability, and plan calendar changes using explicit dates and time zones.
metadata:
  hanni:
    triggers: [schedule a meeting, schedule this meeting, book a meeting, find a meeting time, meeting agenda, calendar, availability, reschedule, time zone, timezone]
---

# Meetings and calendar planning

Identify the meeting's purpose, required participants, duration, date window, and
time zones. Resolve relative dates against the user's current local date and
include the calendar date in proposed times. Account for daylight-saving changes
when translating times across locations.

Read availability using an authorized connected calendar when present. Show only
the scheduling information needed; private event details need not be disclosed.
If access is missing, propose explicitly unverified slots instead of claiming
that participants are free. For an agenda, state the desired outcome, discussion
topics, preparation, and decisions needed, with a feasible time allocation.

Creating, moving, canceling, or inviting people to events requires the user's
instruction for that action. For an authorized change, inspect the current event
and available tool schema, preserve the intended attendees and recurrence, and
check for conflicts before writing. Verify the resulting date, time, time zone,
attendees, and meeting link. Do not claim an invitation was sent from a draft.

Use the task-planning skill for prioritizing work without calendar changes and
recurring-tasks for recurring agent jobs rather than calendar events.

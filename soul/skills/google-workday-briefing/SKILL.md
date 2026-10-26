---
name: google-workday-briefing
description: Assemble an on-demand workday or meeting briefing from the user's connected Google Calendar, Gmail, Tasks and relevant Google Docs.
metadata:
  hanni:
    triggers: [google briefing, google workday, morning briefing, workday briefing, daily work briefing, brief me for work, prepare for my next meeting, meeting prep from google]
---

# Google workday and meeting briefs

Use the user's selected account or the configured account for each service;
label the account for each source. Never widen a request to every account by
default. Establish today's date and timezone from current runtime information.

For a workday brief, read today's events with `google.calendar.events`, a small
relevant Gmail search or recent-message list, and incomplete Google Tasks. Read
specific message bodies only where their contents are needed. For meeting prep,
start with the exact next or selected event; look up related messages and native
Google Docs only when they are relevant to that meeting. Follow returned IDs,
account labels and source links rather than guessing a connection from a title.

Lead with the next fixed commitment, followed by time-sensitive messages, open
tasks and a practical proposed order of work. Attribute deadlines and decisions
to their sources; distinguish your suggested priority from an explicit deadline.
An email action item is not automatically a saved Google task. A calendar title
alone does not establish the meeting agenda or attendees' availability.

If a service is disconnected, denied or partial, name that gap and continue with
the available sources. Do not invent a complete view of the workday. This brief
is read-only: sending email, changing events or saving tasks requires the user's
request and the relevant tool policy. A daily briefing request is not itself a
recurring job; scheduling requires an explicit recurrence request and a successful
schedule receipt.

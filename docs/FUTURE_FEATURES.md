# H.A.N.N.I. Future Features

This document is the running backlog for features we want to add after the V1 foundation is stable.

## Current prioritization (2026-09-24)

Tool Intelligence V1 is **not frozen**. The fresh Language V3 and live Qwen development gates still need work. No capability batch should precede a credible freeze.

| Horizon | Proposal | Family | Risk | Priority | Reason | Dependency |
| --- | --- | --- | --- | --- | --- | --- |
| NOW | Improve broad diagnostic and mixed-request generalization | Routing/tool loop | Read-only | 1 | V3 and Qwen regressions expose real misses | Preserve frozen routing suite and safety tests |
| NOW | Add meaningful model-facing capability coverage cases | Eval | None | 1 | 73 exposed capabilities have no required-tool LLM case | Synthetic output contracts and audited mocks |
| NEXT | Calendar update/delete/free-slot completion | Calendar | Sensitive write | 2 | Existing create/read surface is incomplete | V1 freeze, confirmation and verified outcomes |
| NEXT | Development-environment reads | Developer tools | Read-only | 2 | Support project/build diagnosis | Privacy boundary and coverage fixtures |
| NEXT | LocalForge/server reads | Local services | Read-only | 2 | Observe the owner's local infrastructure | Explicit loopback target and timeout policy |
| NEXT | Background HANNI state engine | Telemetry | Read-only | 3 | Cheap current-state snapshots without repeated LLM calls | Stable tool schemas and resource budgets |
| LATER | LMS/coursework | External account | Credential-sensitive | 3 | Coursework context | Provider access and least-privilege scopes |
| LATER | Server monitoring and Kubernetes | Infrastructure | Read-only initially | 4 | Broader operational awareness | State engine, explicit target inventory |
| LATER | Short-term telemetry history | Local data | Privacy-sensitive | 3 | Answer "what changed 20 minutes ago" | Retention/expiry policy and state engine |
| LATER | Notifications | User attention | Local side effect | 4 | Surface important changes | False-positive controls and quiet hours |
| RESEARCH | HANNI-specific fine-tuned 4B and training dataset | Models/data | Privacy-sensitive | 5 | Improve small-model tool behavior | Consent-safe synthetic/curated data and sealed holdouts |
| RESEARCH | Small laptop, medium, and optional large reasoning models | Models | Resource/cost | 5 | Match different hardware budgets | Same benchmark protocol and explicit placement checks |
| RESEARCH | Local agent harness integration | Automation | High | 5 | Longer tasks after reliable actions | Outcome verification, permissions and rollback design |

## Core Direction

H.A.N.N.I. should evolve from a local voice assistant into a persistent personal AI that can:

- hear and speak naturally
- understand what is happening on the computer
- use tools and applications
- remember useful context
- continue tasks over time
- act proactively when appropriate
- use stronger local or cloud models when needed
- remain privacy-first and user-controlled

---

## Proactive Awareness

H.A.N.N.I. should eventually notice useful events without being explicitly asked every time.

Examples:

- detect when a build fails
- notice when a download finishes
- report when an installation completes
- notice when an application crashes
- warn about low battery
- surface unusually high CPU, RAM, GPU, or disk usage
- notify the user only when something is actually important

The goal is useful awareness without constant interruptions.

---

## Persistent Tasks

H.A.N.N.I. should be able to continue work after the initial request.

Example:

> "Hanni, keep working on this until the tests pass."

H.A.N.N.I. should be able to:

- maintain task state
- retry failed steps
- inspect errors
- safely attempt corrections
- pause and resume work
- report progress
- notify the user when the task completes
- explain what changed

---

## Better Memory

H.A.N.N.I. should maintain useful long-term memory without storing raw conversations forever.

Possible memory categories:

- people
- projects
- preferred applications
- common file locations
- recurring workflows
- user preferences
- past decisions
- task history
- frequently used commands
- device information

Raw microphone audio, raw transcripts, and raw screenshots should continue to follow short privacy retention rules.

---

## Computer-Use Agent

H.A.N.N.I. should eventually move beyond launching applications and be able to interact with software interfaces.

Examples:

- click buttons
- select menus
- fill forms
- navigate applications
- drag and drop
- choose files
- interact with dialogs
- recover when an interface changes
- verify that an intended action actually happened

---

## Screen Understanding Over Time

H.A.N.N.I. should not only understand a single screenshot.

It should eventually understand:

- what changed between screens
- which window changed
- what error appeared
- what dialog replaced the previous one
- what the user is referring to when they say "that"
- screen context from a few minutes earlier without permanently saving raw images

---

## Natural References

H.A.N.N.I. should understand context-dependent commands such as:

- "Open that file."
- "Move this over there."
- "Close the thing I just opened."
- "Use the previous one."
- "Send that to him."
- "Put this in the folder we were using."
- "Try the other option."

This requires task state, object references, memory, and screen awareness.

---

## Multiple Simultaneous Tasks

H.A.N.N.I. should eventually manage more than one task at a time.

Example:

> "Keep downloading that while you fix this project, and tell me when either finishes."

Possible capabilities:

- background task tracking
- priorities
- task cancellation
- status summaries
- resource-aware scheduling
- notifications when a task completes or fails

---

## Specialist Agents

H.A.N.N.I. should remain one user-facing assistant while using specialist agents internally.

Possible specialists:

- coding agent
- research agent
- vision agent
- system-diagnostics agent
- file-management agent
- browser agent
- planner
- critic/reviewer
- memory agent

Workers must not bypass H.A.N.N.I.'s permission and safety layer.

---

## Smarter Model Routing — V2

V2 should add multiple reasoning engines rather than replacing H.A.N.N.I. with one model.

Possible modes:

### Local Only
Everything stays on the user's computer.

### Auto
H.A.N.N.I. chooses the appropriate model based on task difficulty, privacy, latency, and cost.

### Smart Cloud
A stronger cloud model is explicitly used for difficult reasoning.

Possible architecture:

```text
H.A.N.N.I.
    |
Model Router
    |
    +-- Fast local model
    +-- Deep local model
    +-- Vision model
    +-- Coding model
    +-- Optional cloud reasoning model
```

Cloud use should have a privacy gate and should never automatically send sensitive content such as passwords, 2FA codes, banking information, credentials, private browsing content, or raw continuous screen/audio history.

---

## Voice Identification

H.A.N.N.I. should eventually recognize whether the owner is speaking.

Possible behavior:

- owner can execute normal commands
- unknown speakers receive limited or no control permissions
- sensitive actions may require owner verification
- voice identification should not be the only security mechanism for high-impact actions

---

## Speaker-Aware Conversation

When several people are in the room, H.A.N.N.I. should distinguish:

- the owner speaking to H.A.N.N.I.
- the owner speaking to another person
- another person speaking
- background television or media
- H.A.N.N.I.'s own TTS output

---

## Smarter Wake Detection

Future wake detection should use context rather than simple word matching.

Goals:

- recognize Hanni even when STT outputs Hani, Ani, Hanny, Hannie, or Honey
- allow the wake name anywhere in a sentence
- reduce accidental activation when "honey" is used conversationally
- use audio/wake confidence in addition to transcript matching

---

## Original H.A.N.N.I. Voice

Replace the temporary Windows voice with an original H.A.N.N.I. voice.

Desired broad characteristics:

- youthful feminine
- warm
- soft
- bright
- playful
- natural
- clear
- conversational

The voice should be original rather than an exact clone of a real person's voice.

---

## Expressive Speech / Prosody

H.A.N.N.I. should eventually change delivery based on context.

Examples:

- calm warnings
- concise system alerts
- casual conversation
- success confirmation
- serious safety warnings
- lower-energy late-night speech

Avoid making it overly theatrical or gimmicky.

---

## Quiet / Whisper Mode

Possible future behaviors:

- automatically lower volume at night
- respond quietly when the user speaks quietly
- manually enable quiet mode
- avoid loud alerts during meetings or calls

---

## Notification Intelligence

Rather than reading every Windows notification, H.A.N.N.I. should:

- summarize notifications
- prioritize important ones
- suppress low-value noise
- group related notifications
- surface time-sensitive items
- remember which kinds of alerts the user normally ignores

---

## Calendar Integration

H.A.N.N.I. should be able to access and manage the user's calendar.

Core capabilities:

- read upcoming events
- answer "What do I have today?"
- answer "What do I have tomorrow?"
- find events by name, person, date, or time
- create calendar events
- change event dates
- change event times
- reschedule events
- extend or shorten events
- change event titles
- change locations
- add or remove notes
- add or remove reminders
- cancel/delete events when explicitly requested
- detect scheduling conflicts
- check free/busy time
- suggest available meeting times

Example commands:

> "Hanni, move my dentist appointment from Tuesday to Thursday."

> "Hanni, change tomorrow's 3 PM meeting to 4 PM."

> "Hanni, what do I have after lunch?"

> "Hanni, add a two-hour study block Friday evening."

> "Hanni, find me a free hour tomorrow afternoon."

For actions that notify other people, send invitations, cancel shared meetings, or otherwise affect external participants, H.A.N.N.I. should clearly identify the impact before executing when appropriate.

Potential providers can be added through adapters, such as Google Calendar, Microsoft Outlook/Exchange, or other calendar services.

---

## Clipboard / Paste-to-Calendar Academic Workflow

H.A.N.N.I. should be able to accept pasted text from the user and turn it into structured tasks and calendar deadlines.

Primary use case:

The user pastes a summary of class work, an assignment description, syllabus text, LMS content, or a manually written list of due dates.

H.A.N.N.I. should extract:

- course/class name
- assignment or task title
- due date
- due time
- exam/quiz/project type
- submission location if present
- notes or requirements
- priority
- estimated work time when stated

Example pasted text:

> TECH 603 reflection is due September 18 at 11:59 PM. Read Chapter 4 before class. Quiz 2 is September 22.

H.A.N.N.I. could interpret that as:

- TECH 603 Reflection — due Sep 18, 11:59 PM
- Read Chapter 4 — task before next class
- Quiz 2 — Sep 22

Then H.A.N.N.I. should be able to:

- create calendar deadlines
- create reminders before due dates
- create study/work blocks leading up to the deadline
- update an existing event if the due date changes
- avoid creating duplicates
- ask one concise clarification when the class, date, or time is genuinely ambiguous
- summarize what it is about to add before making multiple calendar changes

Example commands:

> "Hanni, I'm going to paste my classwork. Put the due dates on my calendar."

> "Hanni, take this assignment summary and schedule everything."

> "Hanni, this professor changed the paper due date to October 7. Update my calendar."

> "Hanni, add reminders three days and one day before every exam in this list."

Future enhancement:

H.A.N.N.I. could remember course names and recurring class schedules so that phrases such as "before class" or "next lecture" can be resolved automatically.

This feature should support pasted clipboard text first, and later expand to files, screenshots, LMS pages, syllabi, and email.

---

## Clipboard Awareness

H.A.N.N.I. should optionally be able to work with the Windows clipboard.

Possible commands:

- "Hanni, summarize what I just copied."
- "Hanni, explain what's on my clipboard."
- "Hanni, turn this into a checklist."
- "Hanni, save this to my notes."
- "Hanni, put the dates from this on my calendar."
- "Hanni, rewrite what I copied."

Clipboard access should be on-demand or context-aware rather than permanently storing clipboard history.

---

## Academic Assistant

A broader future academic mode could connect calendar, files, memory, and pasted content.

Possible capabilities:

- track assignment deadlines
- remember course names
- maintain a course-by-course task list
- identify upcoming exams
- create study plans
- schedule study blocks around existing calendar events
- summarize syllabi
- extract grading weights
- track major project milestones
- remind the user about assignments that have not been marked complete
- reschedule study time automatically when plans change

H.A.N.N.I. should distinguish between a hard due date and a suggested work/study block.

---

## Email Integration

Possible capabilities:

- search email
- summarize unread or important messages
- find messages by person/topic
- draft replies
- extract dates, tasks, or attachments
- connect email information to calendar/tasks
- identify messages that need follow-up

Sending messages should remain subject to appropriate permissions and confirmation rules.

---

## Phone Companion

H.A.N.N.I. should eventually have a phone interface that connects to the main assistant.

Potential capabilities:

- talk to H.A.N.N.I. remotely
- receive task-completion alerts
- check computer status
- access calendar and reminders
- send a task to the home/desktop H.A.N.N.I.
- securely approve high-impact actions

---

## Secure Remote Computer Control

Future remote capabilities might include:

- start an application
- check whether a task completed
- inspect system health
- restart a safe user-space process
- start a download
- check project/test status
- retrieve a non-sensitive file or summary

Remote access must use strong authentication and conservative permissions.

---

## Home Automation

Possible later integrations:

- lights
- thermostat
- televisions
- smart plugs
- home sensors
- cameras
- door locks
- other smart-home devices

High-impact physical actions should have stronger safety controls.

---

## Personal Dashboard

A dashboard could show:

- H.A.N.N.I. status
- active model
- active tasks
- background tasks
- recent actions
- memory
- CPU/GPU/RAM usage
- vision status
- microphone status
- permissions
- connected services
- privacy mode
- current context
- agent activity

---

## Explain What You Did

After completing an autonomous task, H.A.N.N.I. should be able to give a concise audit.

Example:

> "I changed three files, installed one missing dependency, reran the tests, and all 84 tests now pass."

Detailed logs should still be available when needed.

---

## Undo / Rollback

The user should eventually be able to say:

> "Hanni, undo what you just did."

Possible rollback systems:

- Git for source code
- file backups
- action journals
- reversible tool operations
- restore points for selected configuration changes

---

## Self-Diagnostics

H.A.N.N.I. should detect when one of its own components is failing.

Examples:

- STT unavailable
- TTS failure
- local model server stopped
- vision model unavailable
- microphone disconnected
- tool crashed
- GPU out of memory
- network connection lost
- corrupted configuration

It should attempt safe recovery where possible and clearly report when human intervention is needed.

---

## Self-Updating Components

Long-term, H.A.N.N.I. may:

- discover newer local models
- benchmark candidate models
- compare latency and quality
- recommend upgrades
- update selected dependencies
- test updates before deployment
- automatically roll back failed updates

Critical components should never be silently replaced without a safe rollback path.

---

## Learning Routines

H.A.N.N.I. should notice repeated workflows.

Example:

> "You usually open VS Code and start the local model after opening this project. Want me to do that automatically?"

It should suggest automation rather than silently creating behavioral rules.

---

## Scheduled / Autonomous Routines

Possible routines:

- morning computer setup
- nightly backups
- server health checks
- project test runs
- download monitoring
- dependency checks
- calendar summaries
- assignment reminders
- task reminders
- system maintenance checks

---

## Long-Running Research

H.A.N.N.I. should eventually coordinate multiple agents for research tasks.

Potential flow:

```text
User request
    |
Planner
    |
Research workers
    |
Source comparison
    |
Critic / reviewer
    |
Final H.A.N.N.I. answer
```

---

## Camera Awareness

Optional future webcam support could allow H.A.N.N.I. to:

- inspect an object the user holds up
- understand a physical setup
- read a device indicator
- recognize gestures

Camera access should require stronger privacy controls than normal screen awareness.

---

## Gesture Controls

Potential gestures:

- stop
- mute
- resume
- volume up/down
- acknowledge
- dismiss

These should be optional.

---

## Personality / Interaction Modes

H.A.N.N.I. should remain one assistant while allowing interaction modes such as:

- normal
- concise
- focused work
- coding
- tutoring
- quiet mode
- research mode

The underlying identity and safety behavior should remain consistent.

---

## Offline Survival Mode

When the internet is unavailable, H.A.N.N.I. should still support as much as possible locally:

- wake detection
- STT
- TTS
- local reasoning
- Windows control
- file operations
- memory
- screen awareness
- local vision
- local automation

Cloud-only capabilities should degrade gracefully rather than breaking the assistant.

---

## Desktop / Server Split

A future higher-VRAM desktop or server can run the heavy models while the laptop remains the interactive endpoint.

Possible architecture:

```text
Laptop
- microphone
- speakers
- screen awareness
- Windows tools
- fast local model

        local network

Desktop / Server
- large reasoning model
- coding model
- vision model
- specialist agents
- long-running tasks
```

---

## Multi-Device H.A.N.N.I.

Long-term goal:

One H.A.N.N.I. identity and task state across:

- laptop
- desktop
- phone
- home server
- optional smart-home devices

The user should not feel like they are talking to separate assistants.

---

# Suggested Roadmap Placement

## V1 — Foundation

Focus on reliable basics:

- local voice
- wake / standby
- STT
- TTS
- barge-in
- Windows tools
- screen awareness
- local multi-step agent execution
- memory
- permissions
- privacy
- recovery / hardening

## V2 — Intelligence and Connected Services

Good candidates:

- model router
- optional cloud reasoning
- local-only / auto / smart-cloud modes
- cloud privacy gate
- stronger planning
- calendar integration
- clipboard / paste-to-calendar workflow
- academic assistant
- email integration
- specialist agents
- improved task persistence
- better reference resolution
- smarter proactive awareness

## Later Versions

Good candidates:

- phone companion
- remote computer control
- home automation
- camera awareness
- gesture controls
- advanced voice identity
- custom H.A.N.N.I. voice
- multi-device synchronization
- desktop/server heavy-model architecture
- deeper self-improvement and automated benchmarking

---

# Guiding Principle

The long-term goal is not simply to create a chatbot that talks.

The goal is to combine:

**voice + perception + tools + memory + autonomy + reasoning + persistence**

so H.A.N.N.I. can understand what is happening, act safely, continue work over time, and become a genuinely useful personal assistant.

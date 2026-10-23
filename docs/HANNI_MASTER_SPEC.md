# H.A.N.N.I. Master Specification

## H.A.N.N.I.
**Highly Adaptive Neural Network Intelligence**

## Document Purpose

This document defines the long-term architecture, behavior, goals, and design principles for H.A.N.N.I.

It is the **master source of truth** for what H.A.N.N.I. should ultimately become.

Implementation plans such as `HANNI_V1_IMPLEMENTATION_PLAN_SINGLE_PC.md` define which parts of this vision are built in a specific version.

If an implementation plan and this document conflict:
- The implementation plan controls the current version's scope.
- This master specification controls the long-term direction.
- Major architectural deviations should be explicitly documented.

---

# 1. Vision

H.A.N.N.I. is intended to become a highly capable, local-first personal AI assistant with a natural voice interface, computer awareness, memory, autonomous task execution, and the ability to coordinate multiple specialist AI models when useful.

The ideal experience should feel closer to a personal Jarvis-like assistant than a traditional chatbot.

The user should be able to speak naturally:

> "Hanni, open my project."

> "What's wrong with this?"

> "Fix it."

> "Remind me what we decided yesterday."

> "Take care of this while I work on something else."

H.A.N.N.I. should understand context, inspect the environment, determine an appropriate plan, use tools, verify results, and respond naturally.

---

# 2. Core Identity

H.A.N.N.I. stands for:

**Highly Adaptive Neural Network Intelligence**

H.A.N.N.I. is presented to the user as **one assistant**.

Even if many models, workers, tools, or services operate internally, the user should experience:

- One personality
- One memory
- One conversational identity
- One source of final judgment
- One continuous relationship with the assistant

Specialist models should not present themselves as separate personalities unless explicitly requested.

---

# 3. Core Principles

H.A.N.N.I. should be:

- Local-first
- Voice-first
- Context-aware
- Agentic
- Modular
- Model-agnostic where practical
- Tool-driven
- Event-driven where appropriate
- Interruptible
- Recoverable
- Observable
- Privacy-conscious
- Extensible
- High-autonomy for the authenticated owner
- Conservative around destructive or irreversible actions

---

# 4. Long-Term Architecture

Conceptually:

```text
                         USER
                          |
        +-----------------+------------------+
        |                 |                  |
       Voice            Desktop            Remote
        |                 UI               Interfaces
        +-----------------+------------------+
                          |
                          v
                  +---------------+
                  | H.A.N.N.I.    |
                  | CORE          |
                  +-------+-------+
                          |
        +-----------------+----------------------+
        |                 |                      |
        v                 v                      v
   Supervisor          Memory                  Tools
        |
        +-------------------------+
        |            |            |
        v            v            v
     Vision        Coding       Workers
        |            |            |
        +------------+------------+
                     |
                     v
               Environment
```

The core must not depend on any single interface.

Discord, desktop UI, microphone, mobile app, or future devices should be adapters to H.A.N.N.I. Core rather than the core itself.

---

# 5. Deployment Evolution

H.A.N.N.I. should support staged deployment.

## Initial Deployment

Single Windows computer containing:
- Local microphone
- Local speakers
- Local LLM
- Local STT
- Local TTS
- Screen perception
- Windows tools
- Memory
- Agent loop

## Future Distributed Deployment

H.A.N.N.I. may later use multiple machines.

Potential future roles:

### Core / Server Machine
- Persistent orchestration
- Larger models
- Memory
- Background agents
- Task queues
- Model hosting
- Remote interfaces

### Daily-Use Machine
- Screen perception
- Local audio
- Windows control
- UI Automation
- Foreground interaction
- Low-latency local models

The system should eventually be able to move workloads between machines based on:
- GPU availability
- VRAM
- RAM
- latency
- model size
- active workloads
- task urgency

Distributed architecture is a future capability, not a requirement for early versions.

---

# 6. Primary Interaction Model

Voice is the primary interaction method.

The user should be able to speak naturally without opening a chat window.

H.A.N.N.I. should support:

- Always-available microphone while enabled
- Voice Activity Detection
- Local Speech-to-Text
- Relevance detection
- Conversational follow-ups
- Local Text-to-Speech
- Barge-in / interruption
- Context-aware silence
- Short acknowledgments
- Spoken task status when useful

The wake name **"Hanni"** should be a strong explicit signal but should not be mandatory for every follow-up.

---

# 7. Voice Personality

H.A.N.N.I. should eventually have an original signature voice.

The intended style is:

- Warm
- Youthful
- Friendly
- Soft
- Bright
- Slightly playful
- Natural
- Clear
- Calm during technical work
- More energetic during casual interaction

The final voice should be original and should not imitate or clone a specific real person's biometric voice.

The voice subsystem should support:
- Streaming TTS
- Fast first-audio latency
- Barge-in
- Adjustable speaking rate
- Adjustable expressiveness
- Multiple voice presets
- Future custom voice model integration

Voice development may be maintained as a separate project.

---

# 8. Local-First Requirement

Normal H.A.N.N.I. operation should not require cloud AI services.

Preferred local components:

- LLM inference
- STT
- TTS
- Vision
- Memory
- Tool orchestration
- Event system
- Screen processing
- Computer control

Cloud services may be added later as optional integrations, but H.A.N.N.I. should remain useful without them.

---

# 9. Supervisor Architecture

The Supervisor is the primary H.A.N.N.I. reasoning model.

Responsibilities:

- Conversation
- Intent interpretation
- Planning
- Tool selection
- Delegation decisions
- Context management
- Reviewing worker output
- Final decision-making
- User-facing response generation

The Supervisor should retain:

- Current goal
- Conversation context
- Task state
- User preferences
- Permission state
- Memory access
- Tool authority through the validated tool layer

The Supervisor is the primary "brain" of H.A.N.N.I.

---

# 10. Specialist Model Architecture

As the system matures, H.A.N.N.I. may use specialist models.

Potential roles include:

## Fast Router
- Relevance classification
- Intent detection
- Simple extraction
- Lightweight summarization

## Coding Model
- Code generation
- Debugging
- Repository analysis
- Refactoring
- Testing
- Code review

## Vision Model
- Screenshot interpretation
- UI understanding
- Error/dialog interpretation
- Visual change reasoning

## Reviewer / Critic
- Independent review
- Plan validation
- Code review
- Risk identification

## Memory Model
- Memory extraction
- Summarization
- Retrieval ranking

## Research Model
- Long-context synthesis
- Multi-source analysis
- Structured findings

These roles do not necessarily require one unique model file each.

---

# 11. Dynamic Model Routing

Model selection should be configuration-driven.

Maintain a model registry containing:

- Model name
- Runtime
- Endpoint
- Capabilities
- Context size
- Quantization
- Expected latency
- Memory requirements
- Hardware requirements
- Current availability
- Historical performance

The Supervisor should select models based on:

- Task type
- Task difficulty
- Context length
- Latency requirements
- Hardware load
- Model availability
- Prior model quality
- Resource constraints

Model names should not be hard-coded into core logic.

---

# 12. Resource Management

H.A.N.N.I. should be aware of:

- CPU utilization
- GPU utilization
- VRAM
- RAM
- Model residency
- Active tasks
- Queue depth
- Voice-interaction latency

Interactive voice should receive priority over background work.

H.A.N.N.I. may later:

- Keep small models permanently loaded
- Load specialist models on demand
- Unload idle models
- Pause background jobs
- Move inference to another machine
- Queue large jobs
- Reduce worker concurrency dynamically

---

# 13. Always-Listening Behavior

While H.A.N.N.I. is enabled:

1. Microphone input remains available.
2. Voice Activity Detection identifies speech.
3. Speech is transcribed locally.
4. H.A.N.N.I. decides whether the speech is relevant.
5. Relevant speech is passed to the Supervisor.
6. Irrelevant speech is ignored.

Relevance signals may include:

- Explicit use of "Hanni"
- Direct command grammar
- Direct questions
- Recent conversation state
- Immediate follow-up to H.A.N.N.I.
- Current task context
- Situational urgency

H.A.N.N.I. should prefer silence rather than interrupting unnecessarily.

---

# 14. Barge-In

The user must be able to interrupt H.A.N.N.I.

Examples:

> "Stop."

> "Wait."

> "No, the other one."

> "Don't do that."

While H.A.N.N.I. is speaking:

- VAD continues running
- Owner speech is detected
- TTS stops or ducks quickly
- The new utterance is processed
- The current response or task may be changed/cancelled

Interruption commands receive high priority.

---

# 15. Short-Term Privacy Buffers

The user wants short-term contextual awareness without permanent recording.

## Audio
- Keep only a rolling temporary buffer
- Maximum ordinary retention: **2 minutes**
- Delete expired audio automatically
- Do not create permanent continuous recordings

## Transcript
- Keep a rolling conversational transcript
- Maximum ordinary retention: **2 minutes**
- Delete expired ordinary transcript segments
- Do not permanently archive every spoken conversation

## Screen
- Maintain short-term screen history
- Maximum ordinary retention: **2 minutes**
- Delete expired raw screenshots/frames

Durable memories should contain useful extracted information rather than raw surveillance data.

Current M9 implementation: concise explicit facts and conservative direct-owner
extraction, bounded local retrieval as untrusted context, keyed corrections,
project aliases, and SQLite deletion/cleanup verification. Execution traces are
not durable memories. See `HANNI_M9.md` and D-0024 for current scope and limits;
this implementation does not introduce specialist workers or task restoration.


---

# 16. Screen Awareness

H.A.N.N.I. should understand what the user is viewing.

Target perception frequency:
**approximately one screen sample per second**

This does not mean one vision-model inference per second.

Preferred pipeline:

```text
Screen Capture
     |
     v
Active Window / Metadata
     |
     v
Change Detection
     |
     +---- No meaningful change ----> Lightweight state only
     |
     v
UI Automation / Accessibility
     |
     v
Vision Model when necessary
```

Prefer:

1. Windows UI Automation / accessibility APIs
2. Window/application metadata
3. Screenshot analysis
4. OCR where useful

Vision should be invoked when:
- The user asks about the screen
- A visible error appears
- UI structure is unclear
- A visual task requires understanding
- A meaningful screen change needs interpretation

---

# 17. Privacy Exclusions

H.A.N.N.I. should support sensitive-application exclusions.

Default sensitive categories:

- Password managers
- Credential fields
- Authentication/2FA screens
- Banking applications/sites
- Private/incognito contexts where detectable

When sensitive content is active:

- Avoid vision inference on it
- Avoid screenshot retention
- Avoid durable memory creation
- Use only non-sensitive metadata where practical

The owner may configure additional exclusions.

---

# 18. Computer Control

H.A.N.N.I. should be capable of controlling the owner's computer.

Preferred action order:

1. Application API
2. Command-line / PowerShell
3. Windows UI Automation
4. Browser automation
5. Keyboard/mouse control as fallback

Avoid fragile coordinate-based clicking when a structured method exists.

Potential tool categories:

## System
- CPU/GPU/RAM
- Processes
- Applications
- Active window
- Volume
- Devices
- Services

## Files
- Search
- Read
- Create
- Edit
- Copy
- Move
- Rename
- Delete with safeguards

## Terminal
- PowerShell
- CLI programs
- Development servers
- stdout/stderr capture
- Process tracking

## UI
- Focus windows
- Inspect UI tree
- Activate controls
- Keyboard input
- Mouse input
- Screenshot capture

## Browser
- Playwright or equivalent structured browser automation

---

# 19. Tool Architecture

LLMs must never directly control the computer.

Required flow:

```text
LLM
 |
 v
Structured Tool Request
 |
 v
Tool Registry
 |
 v
Argument Validation
 |
 v
Permission Check
 |
 v
Tool Executor
 |
 v
Structured Result
 |
 v
Supervisor
```

Every tool should define:

- Name
- Description
- Input schema
- Output schema
- Permission level
- Risk level
- Timeout
- Retry policy
- Audit behavior

---

# 20. Autonomy

H.A.N.N.I. is intentionally designed for high owner-approved autonomy.

The assistant should not ask for confirmation before every routine action.

Normally allowed without repeated confirmation:

- Read ordinary files
- Inspect system state
- Inspect screen state
- Open applications
- Run development commands
- Edit project files
- Run tests
- Start/stop development services
- Use browser automation
- Use PowerShell
- Attempt reversible fixes
- Create Git branches
- Delegate tasks
- Perform multi-step workflows

Confirmation should be required for actions with meaningful irreversible or high-impact consequences, such as:

- Bulk permanent deletion
- Disk formatting
- Major security changes
- Credential/password changes
- Financial transactions
- Irreversible account deletion
- Public posting/sending as the user without an explicit instruction
- Kernel/driver-level changes
- Other highly destructive actions

---

# 21. Agentic Behavior

H.A.N.N.I. should not be limited to one command → one action. For local/actionable
requests, the default decision architecture is workflow-first: interpret the goal,
construct a typed one-step-or-many TODO plan, then execute exactly one registered
capability at a time and re-evaluate from real observations. Deterministic routing
may assist capability retrieval but does not bypass planning or the execution/safety
boundary. Calendar access uses Google Calendar only; calendar reads and explicitly owner-requested event creation remain registered capabilities and therefore participate in the same execution/safety boundary.

It should support:

1. Goal interpretation
2. Planning
3. Tool selection
4. Execution
5. Observation
6. Replanning
7. Verification
8. Completion

Example:

> "Hanni, get this project running."

Possible behavior:

1. Determine project
2. Inspect files
3. Check README
4. Inspect dependencies
5. Run startup command
6. Observe failure
7. Analyze logs
8. Fix reversible issue
9. Retry
10. Verify service
11. Report completion

Plans must remain interruptible.

---

# 22. Multi-Agent Delegation

H.A.N.N.I. should eventually delegate when a task is too large, specialized, or parallelizable for one model.

The user should still interact with one H.A.N.N.I.

Conceptual flow:

```text
User
 |
 v
Supervisor
 |
 +--> Coding Worker
 |
 +--> Vision Worker
 |
 +--> Reviewer
 |
 +--> Research Worker
 |
 v
Supervisor reviews results
 |
 v
Tools / final response
```

Delegation triggers may include:

- Large codebase
- Several independent subtasks
- Vision + coding together
- Independent review beneficial
- Large document/context
- Parallel work would save time
- Specialist model has clear advantage

---

# 23. Delegation Limits

Initial long-term defaults:

- Maximum active worker agents: **4**
- Maximum delegation depth: **2**

These limits should be configurable and resource-aware.

Workers may:

- Analyze
- Propose plans
- Generate code
- Review code
- Interpret screenshots
- Return findings

Workers must not bypass the Supervisor's permission/tool boundary.

---

# 24. Task Graph

Complex work should be represented as structured tasks.

A task may contain:

- Task ID
- Goal
- Parent task
- Dependencies
- Assigned worker
- Priority
- Status
- Retry count
- Artifacts
- Findings
- Tool results
- Decisions
- Timestamps

Statuses may include:

- queued
- planning
- running
- blocked
- waiting
- failed
- cancelled
- completed

---

# 25. Memory System

H.A.N.N.I. should distinguish between short-term context and durable memory.

## Ephemeral Memory

Examples:

- Recent transcript
- Recent screen state
- Current task context
- Recent tool results
- Current plan

Raw perception data should expire quickly.

## Durable Memory

Examples:

- Stable user preferences
- Project locations
- Repeated workflows
- Device names
- Important decisions
- Useful corrections
- Long-running project context

Durable memory should be concise and structured.

Avoid storing:
- Passwords
- 2FA codes
- Financial credentials
- Raw continuous audio
- Raw continuous screenshots
- Incidental sensitive content

---

# 26. Explicit Memory Commands

H.A.N.N.I. should support:

> "Remember that..."

> "Forget that..."

> "What do you remember about...?"

> "Show my memories about this project."

> "Delete everything you remember about X."

Deletion should remove both stored records and searchable indexes where applicable.

---

# 27. Proactivity

H.A.N.N.I. should eventually be capable of useful proactive behavior.

Potential triggers:

- Build failure
- Long-running task completion
- Error dialog
- Excessive CPU/GPU load
- Failed background process
- System warning
- Important application state change

Proactivity must be configurable.

H.A.N.N.I. should avoid becoming noisy or intrusive.

---

# 28. Emergency Stop

Emergency control must not depend solely on an LLM.

Primary spoken phrase:

> **"Hanni, stop everything."**

Additional mechanisms:

- Local hotkey
- CLI command
- Desktop UI control in future

Emergency stop should:

1. Cancel active agent tasks
2. Stop queued tool actions
3. Stop active TTS
4. Prevent new autonomous tool execution
5. Enter safe mode

The owner must explicitly clear safe mode.

---

# 29. Failure Recovery

H.A.N.N.I. should be designed to fail safely.

## Model Failure
- Detect unhealthy runtime
- Retry appropriately
- Restart model service where configured
- Use fallback model if available
- Preserve task state
- Inform user when blocked

## Tool Failure
- Capture structured error
- Replan
- Avoid infinite retries
- Avoid repeating destructive actions

## Application Restart
- Restore safe state
- Restore durable memory
- Restore task metadata
- Do not automatically resume dangerous actions

---

# 30. Self-Modification

H.A.N.N.I. may eventually be allowed to improve its own code.

Self-modification must be controlled.

Required principles:

- Use Git
- Preserve known-good state
- Work on a branch
- Run tests
- Run static validation
- Start candidate version separately
- Health check candidate
- Roll back automatically on failure
- Never overwrite the only working copy

Core authorization and safety mechanisms should require explicit owner approval before self-modification.

---

# 31. Auditability

Important actions should be traceable.

Audit entries should include:

- Timestamp
- Task ID
- Actor
- Tool
- Arguments with sensitive values redacted
- Result
- Duration
- Risk level
- Whether confirmation was required
- Whether confirmation was received

Logs must not accidentally become permanent copies of raw microphone or screenshot history.

---

# 32. Event-Driven Core

Potential events include:

```text
VOICE_ACTIVITY_STARTED
VOICE_ACTIVITY_ENDED
TRANSCRIPT_READY
OWNER_COMMAND
SCREEN_CHANGED
ACTIVE_WINDOW_CHANGED
MODEL_STARTED
MODEL_FAILED
TASK_CREATED
TASK_UPDATED
TASK_COMPLETED
TOOL_REQUESTED
TOOL_COMPLETED
TOOL_FAILED
MEMORY_CREATED
SYSTEM_ALERT
EMERGENCY_STOP
HANNI_STARTED
HANNI_STOPPED
```

Structured event schemas should allow tracing across components.

---

# 33. Interface Roadmap

H.A.N.N.I. interfaces should be modular.

## V1
- Local microphone
- Local speakers
- CLI for debugging/admin

## Future
- System tray interface
- Desktop application
- Discord
- Mobile app
- Web dashboard
- Remote control interface
- Smart-home interfaces
- Wearable interfaces

No interface should become a hard dependency of H.A.N.N.I. Core.

---

# 34. Future Desktop Experience

A future desktop interface may show:

```text
H.A.N.N.I.

● Listening
● Supervisor Online
● Vision Ready
● Tools Enabled

Current Task
────────────────────
Fix development project

✓ Inspected repository
✓ Reproduced error
> Testing fix
○ Verify
○ Complete

Agents: 2 active

[ Pause ] [ Stop ] [ Details ]
```

The ideal future experience does not require the user to open the interface for normal voice interaction.

---

# 35. Future Discord Role

Discord may return later as a remote interface.

Potential uses:

- Remote text commands
- Task status
- Logs
- Notifications
- Voice access while away from the computer
- Long-running task updates

Discord should remain an adapter, not H.A.N.N.I. Core.

---

# 36. Future Multi-Computer Role

The previously considered server PC may later be used for:

- Larger model hosting
- Persistent background tasks
- Memory services
- Long-running coding agents
- Offloading inference
- Remote access
- Redundancy

The single-PC version should not be implemented in a way that prevents future distribution.

---

# 37. Security Boundary

Authorization must exist outside the LLM.

Do not trust model-generated claims such as:

> "The user approved this."

The system itself must know:

- Who requested the action
- What permission applies
- Whether confirmation is required
- Whether approval was actually given

Sensitive tool execution must be enforced in code.

---

# 38. Configuration

Configuration should remain external to source code.

Examples:

```text
config/
  hanni.yaml
  models.yaml
  permissions.yaml
  privacy.yaml
```

Model files, endpoints, thresholds, retention periods, and tool policies should be configurable.

Secrets should use:

- environment variables
- OS credential stores
- future secure vault integration

Never commit real secrets.

---

# 39. Suggested Technology Stack

Initial technologies may include:

## Core
- Python 3.12+
- asyncio
- Pydantic or equivalent validation
- SQLite

## LLM
- llama.cpp
- OpenAI-compatible local API where practical

## STT
- faster-whisper
- whisper.cpp as alternative

## VAD
- Silero VAD
- WebRTC VAD as alternative

## TTS
- Modular local TTS interface
- Engine chosen through benchmarking

## Vision
- Local multimodal model
- Windows screen capture
- UI Automation

## Windows
- PowerShell
- psutil
- Windows APIs
- UI Automation

## Browser
- Playwright

Technology choices are replaceable implementation details, not permanent architectural constraints.

---

# 40. Development Philosophy

Build H.A.N.N.I. vertically and incrementally.

Prefer:

```text
Small feature
    |
    v
Actually works
    |
    v
Tested
    |
    v
Next feature
```

Avoid:

```text
Massive architecture
    |
    v
Months of infrastructure
    |
    v
Nothing the user can actually talk to
```

The project should reach a useful conversational assistant as early as possible.

---

# 41. Current Implementation Direction

The current implementation plan is:

`HANNI_V1_IMPLEMENTATION_PLAN_SINGLE_PC.md`

That document intentionally simplifies V1 to:

- One Windows laptop
- Local microphone
- Local STT
- Local Supervisor LLM
- Local TTS
- Windows control
- Screen awareness
- Memory
- Agent loop
- Specialist delegation later

Discord, the second server PC, and distributed networking are deferred.

---

# 42. Instructions for AI Coding Assistants

When working on H.A.N.N.I.:

1. Read this master specification.
2. Read the active version implementation plan.
3. Read `CLAUDE.md` or equivalent project instructions.
4. Respect the active version's scope.
5. Do not silently redesign major architecture.
6. Inspect existing code before modifying it.
7. Keep modules replaceable.
8. Keep interfaces separated from H.A.N.N.I. Core.
9. Keep LLM reasoning separated from permission enforcement.
10. Validate all tool arguments.
11. Test important behavior.
12. Preserve privacy-buffer requirements.
13. Preserve emergency-stop capability.
14. Avoid cloud AI dependencies unless explicitly approved.
15. Do not over-engineer future features during early milestones.
16. Keep future distributed operation possible without forcing it into V1.
17. Prefer working vertical slices over speculative infrastructure.
18. Explain major deviations before implementing them.
19. Maintain documentation when architecture changes.
20. Stop at milestone boundaries when the active plan requires owner approval.

---

# 43. Definition of Success

H.A.N.N.I. succeeds when the user can interact with it as a persistent intelligent assistant rather than a chatbot.

The long-term experience should be:

- Speak naturally
- Be understood
- Be remembered appropriately
- Be able to ask what is on screen
- Ask for computer tasks
- Hand off larger goals
- Interrupt at any time
- Trust that H.A.N.N.I. can act
- Understand what H.A.N.N.I. is doing
- Retain ultimate control

The technology should disappear behind the experience.

The user should not need to think in terms of prompts, APIs, models, agents, or tools.

They should simply be able to say:

> **"Hanni..."**

and continue naturally.

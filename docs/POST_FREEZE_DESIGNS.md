# Post-freeze state, history, and proactive design

These are designs for later phases. Tool Intelligence V1 has not been declared
frozen, so no new capability batch or background collector is implemented here.

## State Engine

A future read-only collector can maintain typed snapshots of CPU, RAM, GPU,
processes, disks, model health, app presence, and connected local services.
Each field needs a source capability, observed timestamp, age/TTL, confidence,
and explicit error/partial-state value. Collection should be periodic and
adaptive: cheap host counters more often, expensive process/disk probes only
when needed, and no LLM invocation. The model gets a bounded view with freshness
labels; a stale or missing field is never presented as current fact. Reuse the
existing capability registry and permission boundary. Do not grant background
mutation authority.

## Historical state

Once snapshots are trustworthy, retain a bounded, local, privacy-reviewed
time series with retention and deletion controls. Store numeric telemetry and
limited process identity only when the owner opts in. Correlate “why did my PC
slow down 20 minutes ago?” by comparing timestamps and changes; distinguish
co-occurrence from cause. Do not retain raw conversations, file contents, mail,
calendar details, OAuth material, or tool secrets in telemetry history. Keep
the current session conversation cache separate from durable history.

## Proactive assistance

Start with explicit opt-in and narrow read-only triggers: sustained resource
pressure or a confirmed local model failure. Require repeated measurements,
cooldowns, deduplication, quiet hours, and a visible reason for each alert.
Never infer emergencies from one ambiguous sample. Proactive observation does
not authorize process termination, file deletion, account writes, or outbound
messages. Measure false alerts and owner dismissal rate before broadening.

## Capability boundaries

Future Google Calendar completion, development-environment, and LocalForge
awareness should be small named capabilities with explicit input/output schemas,
risk classification, and regression cases. Avoid a general `system.do_anything`,
arbitrary shell, or generic browser automation tool. New batches wait for a
measured Tool Intelligence V1 freeze gate.

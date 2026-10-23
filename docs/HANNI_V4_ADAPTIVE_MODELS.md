# HANNI V4.0 adaptive models

HANNI now selects inference endpoints through its existing controller, using
measured capabilities, tested context limits, protected sharing permissions,
health and load. The original tool registry, MCP host, approvals and workflow
execution remain authoritative. Model output never grants tool permissions.

## Use and configuration

Open **Mission Control → Model Routing** in the existing HANNI desktop. The view
shows registered endpoints, verified limits, current requests, category profiles,
recent choices, excluded endpoints and fallback events. Endpoint refresh performs
bounded background health checks; it does not start or replace a model server.
Failed page loads have a Retry loading action.

Balanced, Fast, Quality and Manual override are supported. Each policy first applies
the same eligibility checks. Manual selects a preference, and cannot override
privacy, health, capacity or capability checks. Policy changes pass through the
existing local capability registry, token/Origin checks and Safe Mode. They do not
authorize remote sharing or edit measured capability receipts.

The defaults in `config/hanni.yaml` are:

```yaml
model_routing:
  policy: balanced
  max_fallbacks: 2
  max_queue_seconds: 5
  minimum_samples: 20
  minimum_accuracy_lower_bound: 0.7
```

Saved desktop preferences persist across sessions. Deliberately changing the
configured default resets the saved preference. Quality ranking requires at least
20 graded samples in the requested category and a Wilson 95% accuracy lower bound
of 0.7. The current small benchmark does not meet that threshold. With insufficient
evidence, HANNI preserves conservative default ordering. Ungraded live responses
contribute latency measurements without inventing correctness scores.

## Controller and workflows

`hanni.models.adaptive.AdaptiveModelEngine` wraps the original model client when
the real controller attaches. Dashboard sessions share the existing compute
scheduler and engine rather than creating a second inference authority. Isolated
sessions are keyed by their data directory, and close only services they own.

Text, memory, MCP and planning requests receive trusted context categories from
their original controller paths. Workflow analysis uses the original admission
guards and evidence verifier. The current remote worker definitions authorize
synthetic analysis only. Ordinary conversations, memories, screen content and
private workflow inputs therefore remain on authorized local inference.

Remote native function-call format was tested independently, but the existing
distributed transport authorizes pure analysis. A successful format probe does
not authorize remote HANNI tool generation or execution. Unsupported operations
are excluded. Local native calls retain their original MCP schema validation and
permission checks.

Fallback retries pure inference only. Observable causes include endpoint/timeout
failure, unsupported context, rejected structured output and external task
verification failure. Admission, identity and sharing checks repeat before each
dispatch. The default permits three total inference attempts. A model's stated
confidence does not trigger escalation. Streaming never replays an inference
after a visible output chunk, and fallback never repeats a side-effecting tool.

## Measurements and identity

The protected database is `data/model-routing/profiles.sqlite3`. It stores
capability receipts, per-category measurements, settings and bounded decision
history. It does not store raw prompts, answers, memories or credentials.
Evaluation environments, graded denominators and confidence are explicit.
Per-category resource observations persist known available RAM, free VRAM, active
requests, queue depth and sample time. The profile aggregates known values with
sample counts, mean, minimum and maximum; missing values remain null. These are
admission snapshots, not peak process consumption or minimum model requirements.
Completed and interrupted streaming contributes ungraded telemetry without
inflating task accuracy. Cancellation releases the active slot without replay.

Configured context is distinct from verified context. Request admission accounts
for messages, schemas and output; conservative byte bounds can reject some
otherwise token-compatible inputs. Unknown context, vision, memory requirements
and quality remain unknown. The original configured primary can retain its
explicitly labeled legacy path while unverified; that grants no new remote,
vision or enlarged-context capability.

Evidence is bound to deployment and observed runtime identity. Full GGUF content
fingerprints are cached against size, modification time, change time and inode;
remote model/backend fingerprints use the original strict SSH transport. Ordinary
same-name file replacements invalidate the evidence. Local server binary content is not independently hashed; local backend binding
uses reported build/template metadata and configured runtime settings.
Fingerprinting is read-only,
restricted to configured files and approved existing model directories. Strata's
existing model directory received a narrowly scoped protected fingerprint root;
its serving configuration and sharing categories were preserved. Initial remote
full-file hashing can take minutes, and runs in the background so local controller
startup does not wait for it.

Availability and resource snapshots describe the observation time. Configured
RAM/VRAM budgets are not measured memory requirements. The UI labels them
separately. Historical context receipts without the current strong runtime binding
remain historical evidence and cannot authorize current adaptive dispatch.

## Validation and continuation

See [implementation checkpoints](HANNI_V4_CHECKPOINTS.md),
[benchmark comparison](HANNI_V4_BENCHMARK_COMPARISON.md), and the
[independent V4 review](v40-reviews/INDEPENDENT_REVIEW.md) for actual benchmark,
regression and security results. Small synthetic
holdouts demonstrate behavior on those tasks, not general model superiority or
production autonomous reliability. The resident primary was not changed.

To resume, inspect the checkpoint and working diff first. Reuse the original
controller/compute services, keep evidence under protected ignored `data`, and
never promote configuration values into measured claims. The scripts in
`scripts/v40_verification` require explicitly owned local/remote serving sessions;
do not launch or kill an unrelated process. Repeated tests of a sealed holdout are
regression rechecks, not newly unseen evaluations. Import measured profiles only
after prospective decisions are sealed, using identity-bound engineering APIs.
No desktop endpoint accepts evidence imports or sharing grants.

Run `.venv\Scripts\python.exe -X utf8 -m pytest` for the repository suite and
`npm run build` in `frontend` for TypeScript and packaged desktop assets. Packaging
includes the compute module, adaptive engine, routing view and local Geist Sans
font/licenses. No mandatory cloud dependency, model download or repository push
was introduced.

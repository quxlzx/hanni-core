# Learning from work

Open **Agent tools → Skills**. The page separates Library, Review, Journey, Learning settings, and Training data.

HANNI learns by saving instructions and personal notes. These features do not change model weights.

## Capture a working procedure

The native agent can use `skill_propose` after a useful workflow, error recovery, or owner correction. A proposal includes the procedure, working commands and tool usage, trigger keywords, pitfalls, verification evidence, and the correction that motivated it. It should update a relevant existing skill rather than create a duplicate. Verification text is a claim backed by the source task; it is not a runtime certification.

Proposals appear in **Skills → Review** with a diff and source information. Inspect the source snapshot or task receipts before accepting. Rejected proposals do not become instructions. Accepting an outdated proposal fails if the current skill changed. Existing `skill_save` remains available through the ordinary write-permission and action-review path; its revisions and source task also appear in the journey.

Use **Library → a skill name → Edit procedure** to make a correction and stage a new diff. **Create skill** uses the same review path. Bundled procedures are preserved in the repository; an accepted correction creates a learned override under the local data directory.

## Separate background review

`/refine [focus]` starts a bounded model request against an immutable conversation snapshot. The review has its own messages, receives no tool registry, and cannot execute commands or edit the active conversation. Continue chatting while it runs. **Review snapshot** in Skills provides the same operation with a conversation selector.

Automatic review is enabled by default after **8 new completed exchanges**, with at least **300 seconds** between reviews of the same conversation. Change or disable it under **Learning settings**. Existing history is seeded as already counted when the feature is first installed; use `/refine` to review it explicitly. Automatic requests start while the chat inbox is idle. The review uses the selected inference provider, including that provider's normal costs and handling of supplied conversation excerpts, memories, and tool observations.

Reviews request schema-constrained JSON, disable local-model thinking for that structured response, use a 60-second network timeout without timeout retries, and cap output at 5,000 tokens. A provider that explicitly rejects structured output gets one ordinary JSON-prompt request on the same provider; its output still requires validation. It can propose at most three skills and five memory changes. Bad output, unavailable providers, unknown evidence IDs, and stale revisions produce an inspectable failure. There is no automatic fallback to a different provider. Review IDs, source snapshots, outcomes, and successful-review watermarks persist across restarts. An interrupted review is marked interrupted and is not replayed.

**Cancel review**, `/stop`, or backend shutdown requests cancellation. An in-flight model HTTP request may still finish, but cancellation checked before staging prevents late proposals. Proposals already staged remain available for review. Automatic-review settings do not disable an explicit `/refine` request.

## Facts, procedures, and history

- Compact facts and preferences use the existing persistent memory store. The reviewer proposes additions or explicit corrections, each tied to owner message IDs. **Accept memory** can apply edited text; **Reject memory** leaves stored facts unchanged. The existing Memory page also supports inspection, correction, and forgetting.
- Reusable procedures use versioned skills, loaded only when matched or explicitly read. Runtime application, explicit views, and patches have separate counters. Repeated application within the same task is counted once.
- Detailed conversations stay in searchable session history. The native `session_search` tool is an alias of the existing bounded `history_search`; it returns excerpts and conversation IDs. The active task journal remains separate.

`/journey` and **Skills → Journey** show skill changes, saved memory updates and retained correction history, and review outcomes. This is an activity timeline, not a replacement for the Memory page or full searchable conversation history. Deleted memory contents are not reconstructed into it.

## Maintain accumulated skills

`/curator dry-run` or **Preview maintenance** shows deterministic changes without applying them. `/curator` or **Run maintenance** marks learned skills stale after **14 days** without a view, application, or patch, and archives them after **30 days**. Archives are logical: the entire original skill package stays on disk and disappears from task matching until **Library → Include archived → Restore**.

Bundled skills are never automatically pruned. Pinned skills and skills named in saved repeating-task prompts are protected, including paused schedules. Support files are retained with their packages. Curator errors reading schedules prevent that maintenance pass; they are not treated as permission to archive referenced skills.

Automatic maintenance first waits one full interval (**168 hours** by default) and runs after at least **two hours** without chat activity. Adjust the interval and age thresholds in Learning settings. **Pin** protects an important learned procedure from maintenance; an explicit owner Archive action remains available.

Model-based consolidation is **off by default**. `/curator consolidate` or **Propose skill consolidation** requests one bounded model review. It can stage a maintained or consolidated procedure with exact source revisions. Accepting that diff also archives the displayed absorbed skills. The original packages remain recoverable. Bundled, pinned, schedule-referenced, archived, and support-file packages cannot be absorbed. A source that becomes protected or changes before acceptance blocks the consolidation.

## Collect training data

**Training data → Queue read-only batch** accepts one prompt per line, up to 20 prompts. Each runs as a separately persisted native task with its own messages and working state. The batch has a fixed read-only tool scope; writes, terminal/code execution, schedules, delegation, and skill mutations are excluded. The running native bridge supervises execution with ordinary cancellation, iteration limits, provider handling, and receipts. Existing tool-access policy may restrict it further. **Cancel batch** withdraws unfinished work without erasing completed results.

A terminal alternative accepts a JSONL file containing `{"prompt":"..."}` on each line:

```powershell
.\.venv\Scripts\python.exe -m hanni.native.training --root state batch .\prompts.jsonl --id endpoint-study-1
.\.venv\Scripts\python.exe -m hanni.native.training --root state list
.\.venv\Scripts\python.exe -m hanni.native.training --root state cancel endpoint-study-1
.\.venv\Scripts\python.exe -m hanni.native.training --root state export --batch endpoint-study-1 --format trajectory --output .\trajectories.jsonl
```

Resubmitting the same batch ID and prompt list retrieves its existing task IDs. A different list with the same ID is rejected. The bridge must be running to execute queued tasks. The terminal command is an explicit local owner action.

Exports are available for one batch or the latest 50 finished tasks, as HANNI trajectory JSONL or ShareGPT JSONL. They preserve complete tool-call/result groups and receipts, omit orphaned groups and system messages, and exclude separate reasoning fields and inline assistant `<think>` sections. Credential redaction is applied recursively, including serialized tool arguments/results. Other private task, document, and memory content can remain; inspect the file before sharing it. The export is capped at 8 MiB and never uploads itself. Missing checkpoints are omitted rather than invented. Compression may mean the checkpoint contains a compacted trajectory rather than every original turn. Rewards are unassigned and `verified_success` remains false; a completed assistant response is not proof of task success.

## Offline Atropos bridge

`scripts/export_atropos.py` converts HANNI trajectory exports into Atropos `ScoredDataGroup` JSONL. Use a separate training environment with `transformers` installed and an existing local tokenizer. The converter loads no remote tokenizer code or model weights.

Provide a JSON object mapping every trajectory ID to a numeric reward you have explicitly reviewed, for example `{"trajectory-id":0.75}`:

```powershell
python scripts/export_atropos.py --input .\trajectories.jsonl --labels .\reviewed-rewards.json --tokenizer C:\Models\tokenizer --output .\atropos-groups.jsonl
```

The converter groups identical initial prompts, retains tool context, verifies the exact tokenizer prompt prefix, and masks only the final assistant answer. It rejects missing/nonfinite rewards or incompatible token alignment. The output can be consumed from a separate Atropos environment or training pipeline. It does not provide on-policy rollouts, infer rewards, launch an RL service, or train weights. End-to-end RL training and model improvement have not been validated by HANNI's app tests.

The adapter follows the official [Atropos ScoredDataGroup contract](https://github.com/NousResearch/atropos/blob/main/atroposlib/envs/base.py) and [token masking examples](https://github.com/NousResearch/atropos/blob/main/environments/math_server.py). Hermes documents the related [skill workflow](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills), [curator](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator), and [batch trajectory generation](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/batch-processing.md). HANNI implements these features in its native runtime rather than depending on a Codex runtime or Hermes installation.

## Local storage and verification

The configured data directory holds `skills/`, `skill-revisions.sqlite3`, `learning.sqlite3`, and `training.sqlite3`, alongside existing memory, conversation, and task databases. These runtime files are ignored by Git. Proposal review and settings changes use the dashboard's token, same-origin checks, original owner permissions, Safe Mode checks, and private audit path. Read-only tool access still allows the agent to stage an inactive skill proposal; it cannot activate the skill.

Automated tests exercise real SQLite persistence, skill activation/conflicts, source validation, cancellation, protected curation, archive recovery, batch scoping, HTTP authorization, export redaction and token alignment. Browser checks use the real local endpoints and stores with an isolated model boundary. Model-generated procedure quality and downstream training gains still require evaluation on your actual work.

A smoke test with the running local model completed a real structured review of a synthetic conversation and staged a personal-memory suggestion without activating it. This checks the local provider path, not the quality of procedures learned from arbitrary work.

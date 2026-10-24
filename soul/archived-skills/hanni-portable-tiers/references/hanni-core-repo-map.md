# HANNI-Core target repo: <owner>/HANNI (GitHub)

Standing decision: the standalone HANNI agent is built on the user's EXISTING repo `<owner>/HANNI` — never scaffold a fresh repo for this work. The frontend and backend skeleton already exist; the project is a bridge replacement, not a greenfield build.

## Repo layout (verified via GitHub MCP, Oct 2026)
- `frontend/` — Vite + React/TS control deck (~40 components): model_lab, model_routing, inference_control, mcp_hub, memory, workflows, cluster, compute, execution_trace, awareness, productivity, workspace. This IS the HANNI interface — reuse as-is.
- `src/hanni/` — Python backend package: `core/` (orchestrator, interaction, identity, response_stream/style, state, events, health, activity, notifications, shutdown), `hermes/` (client, session, service, worker, tunnel, schema_guard — the CURRENT brain bridge to Hermes), `memory/`, `tools/`, `models/`, `mcp/`, `speech/`, `compute/`, `reliability/`, `evals/`, `workflows/`, `dashboard/`, `cli.py`.
- Windows-first conveniences (`*.cmd` setup/start scripts) but the core is Python — runs on Linux unchanged.
- Related repos: `<owner>/HANNI_NEGATIVE_SIGNALS_LLM_FINAL_ROUTING` (private, routing evals on the laptop), `<owner>/hanni-agent-cluster` (private, older).

## The surgery (agreed plan)
1. Clone to yunjin; audit `core/orchestrator.py` + `hermes/worker.py` to find the exact brain-call seam.
2. Build `src/hanni/native/`: prompt assembly (repo `identity.py` + HANNI SOUL.md/memories from `~/.hanni`) → tool-calling loop against Wonyoung Strata (or tier llama-server) → tool execution through repo `tools/` → stream into the frontend.
3. Feature-flag `hermes` bridge vs `native`; flip when native matches, then retire Hermes as the runtime (keep it as boot loader during transition).

## Soul files to carry in (unchanged formats)
`~/.hanni/SOUL.md` (~820 tok), `memories/`, `skills/` (markdown + frontmatter), `state.db` schema — the repo's memory/identity layers should read these formats so migration day is a config flip, not a rewrite.

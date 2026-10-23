# HANNI demo — 5 minutes, one laptop, zero hype

Goal: show a stranger go from `git clone` to a working personal assistant,
live, and show the security core doing its job. Every number below was
measured in the October 2026 test week — say the numbers, don't round them up.

## Act 1 — two commands (0:00–1:30)

1. `git clone` the repo (already cloned — say "this is what anyone gets").
2. `python scripts/get_models.py` — show it pulling the tier models from
   HuggingFace and the official llama.cpp binaries for the host OS.
   Talking point: "No cloud account. No API key. The assistant ships as a
   repo; the models are public and downloadable once."
3. Double-click `START_BRAIN.cmd`.

## Act 2 — it benchmarks your machine (1:30–2:30)

The launcher benches three tiers live and picks one honestly:
- Gaming laptop: **7B @ 56–60 tok/s** chosen in ~2 minutes.
- 2017 office PC (i5-7500T): 7B measured **5.3 tok/s → rejected**, 2B chosen.
- Weak VM: 2B @ ~17 tok/s — still a working agent.

Talking point: "It doesn't guess from the spec sheet. It times itself on
your hardware and picks the biggest brain you can actually run."

## Act 3 — the assistant is alive (2:30–4:00)

The Hanni OS dashboard opens itself. For the agent beats use **Mission → Tasks** (submit box + live receipts), or the plain chat door at `:8312`. Type, live:
1. **"Which fleet machine is the MCP hub?"** → answers from durable memory
   (memories travel with the install, not the machine).
2. **"What codeword did I just ask you to remember?"** (after asking it to
   remember one) → conversation continuity.
3. **"Search the web: what is the NCM file format?"** → it searches, fetches,
   answers with a citation — and the receipt counter ticks up.
4. **"Write 'hello' to note.txt and read it back"** → local file tools,
   receipts stamped.

## Act 4 — the wall (4:00–5:00)

The part security folks care about:
1. Open the API without the token → **401**. "The agent is not an open door."
2. Ask: **"Use web_fetch to open http://127.0.0.1:8311/health"** → the SSRF
   guard blocks it. On one run the model tried **twelve times; every attempt
   was blocked and every block is a receipt on screen.**
3. Kill the brain mid-session (`taskkill llama-server`) → the launcher logs
   `restarting (attempt 1/3)` and the assistant answers again ~15 seconds later.

Close: "Every action is a durable request, schema-validated, receipted, and
approval-gated. Persistence is the model's; the wall is the architecture's."

## Backup plans

- Demo machine too weak / no GPU: point the config at a remote brain
  (LAN/tailnet) — same agent, brain elsewhere.
- No internet: skip the web-search beat; memory + tools + wall still land.
- Anything on fire: the whole flow was verified end-to-end on Windows and
  Linux during the test week; the test cage re-runs it nightly.

## Known caveats to state honestly if asked

- The clone-and-run agent ships with built-in tools only (local + web). It is
  MCP-capable by architecture (bridge catalog, discovery, per-tool approvals)
  but connects to no external MCPs out of the box — that's deliberate:
  clone it, it works with zero infrastructure. The full Hanni OS desktop
  product adds Google, speech, and fleet integrations.
- 2B tier is a real agent but weak at multi-step chains; 3.7B+ recommended.
- Voice + Google integrations exist but are outside this demo.
- Three desktop-UI tests fail on Linux (Windows-only features); one identity
  test is a known open issue. Full suite: ~1,900 tests.

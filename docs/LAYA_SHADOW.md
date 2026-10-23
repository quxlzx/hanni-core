# Laya shadow mode inside HANNI

**This is opt-in experimental instrumentation, not an autonomous memory manager.**

HANNI now contains `src/hanni/laya/` (the client, private read-only sidecar,
training-time question contract, and launcher-managed lifecycle). The existing
memory store, privacy gate, retrieval, and permission controller are unchanged.
Laya receives a copy of an *authorized owner's text turn* for inference and
writes **only prediction metadata** to a private audit file on the inference
machine. It cannot access memory databases, issue tools, reply to the user,
return memory actions, or modify memory. The normal HANNI path always wins.

The checkpoint's challenge accuracy was **64% capture, 71.43% relevance, 66.67%
relations, 90% sensitive, 70% importance within tolerance**, against
**unreviewed draft labels**. Do not use its scores for permissions or privacy
security decisions. Inference confidence is uncalibrated.

## Public source and private data

The public repo includes Laya integration and model-adapter code. It **does not
include** Laya weights, ROCm/PyTorch binaries, personal conversation exports,
private dataset labels, `.env`, credentials, SSH keys, or local shadow audit logs.
Model downloads must comply with the original model and Laya runtime licenses.
No extra Python dependencies are required to run ordinary HANNI without Laya.

## One-command startup on the developer's Windows HANNI desktop

**One-time steps only:** On Wonyoung, retain the existing `~/hanni-laya`
installation, its `.venv-rocm`, the existing `hanni_laya_shadow` Python service,
and `~/hanni-laya-models/laya-general-v2`. You do not need to keep a terminal
open on Wonyoung; HANNI's launcher can start the remote server if it isn't
running. The optional code in this repo is the replacement for new users; on
Wonyoung, the already-installed sidecar is still compatible.

Configure **SSH key authentication** from Windows to the GPU machine first.
The launcher uses `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes`: no
password prompt, no accepting unknown host keys. Verify the machine's host key
out of band and establish `known_hosts` before enabling Laya. Normal HANNI
works even if the machine is offline, the key is absent, or no GPU is available.

1. Copy `.env.example` to `.env` (local file, ignored by Git).
2. Set these values in `.env`, replacing the host with your own private address:

   ```dotenv
   HANNI_LAYA_SHADOW_ENABLED=1
   HANNI_LAYA_TRANSPORT=remote-ssh
   HANNI_LAYA_ALLOW_REMOTE_TEXT=1
   HANNI_LAYA_SSH_HOST=wonyoung@YOUR_PRIVATE_SSH_ADDRESS
   HANNI_LAYA_LOCAL_PORT=8766
   HANNI_LAYA_REMOTE_PORT=8765
   ```

   If needed, set `HANNI_LAYA_SSH_IDENTITY` to a private SSH key **path**, not
   the key contents. Set `HANNI_LAYA_REMOTE_COMMAND` only if the default Wonyoung
   directory or Python executable differs. The provided default command is:

   ```bash
   cd ~/hanni-laya && exec .venv-rocm/bin/python -m hanni_laya_shadow.server --model ~/hanni-laya-models/laya-general-v2 --port 8765
   ```

3. Run **`START_HANNI.cmd`** as usual. It starts the existing dashboard, Qwen
   model, voice and tool pipeline; it also launches Laya's SSH tunnel in the
   background. If the remote sidecar is already healthy it is reused; otherwise
   HANNI attempts to start it on Wonyoung via SSH. Startup never waits for Laya.
   Ctrl+C on Windows shuts down connections it started. The remote model is
   not bundled in the public source ZIP.

**Important:** Set `HANNI_LAYA_ALLOW_REMOTE_TEXT=1` only if you consent to
sending owner turns from your Windows desktop to your **own** remote machine.
Text is carried through an encrypted SSH tunnel, served on loopback only,
and authenticated with a token read from the remote machine over SSH. The
controller filters known secret/safety patterns and limits payload size, but
cannot guarantee detection of every type of personal information. Disable
shadow mode for conversations you do not wish to send to another machine.
No raw text is written by the Laya shadow audit module.

## Local inference alternative

With a compatible installed `laya` Python runtime and private checkpoint on
one machine:

```dotenv
HANNI_LAYA_SHADOW_ENABLED=1
HANNI_LAYA_TRANSPORT=local
HANNI_LAYA_MODEL_PATH=/absolute/path/to/your/laya-general-v2
HANNI_LAYA_LOCAL_PORT=8766
```

The launcher starts `python -m hanni.laya.server` if no authenticated
compatible local sidecar is already running. `laya` is an **optional runtime**:
we intentionally don't install PyTorch/ROCm into Windows HANNI by default.
For a Linux headless session you can also manually use:

```bash
python -m hanni.laya.server --model /private/path/to/checkpoint --port 8765
python -m hanni.laya.report
```

In local mode the bearer token lives at `~/.config/hanni/laya-shadow.token`.
In remote mode, the token never needs to be pasted into Windows `.env`.

## Technical limits and operation

- `MemoryAwareSession` submits bounded, sanitized text to an independent
  background queue on each nonempty owner turn. This covers chat, text and
  voice flows wrapped by the current memory session. No transcript window,
  screen capture, tool response, or stored memory database is forwarded.
- No memory text is sent for pairwise relation/relevance tasks yet. The shadow
  log presently contains only capture, sensitivity and importance predictions.
  Pairwise reasoning will require a separately permissioned, privacy-reviewed
  candidate-memory boundary in a later release.
- The remote sidecar returns an acknowledgement with **no model prediction**.
  Dropped observations, SSH failures, a full queue, and a GPU outage cannot
  affect the real HANNI result. Safe Mode suppresses turn observation.
- The sidecar is loopback-only, bearer-authenticated, and logs metadata
  locally under `~/.local/state/hanni-laya-shadow/decisions.jsonl` by default.
- To stop Laya: set `HANNI_LAYA_SHADOW_ENABLED=0` and restart HANNI.
- Status/logs on the GPU box: `python -m hanni_laya_shadow.report` for the
  existing sidecar, or `python -m hanni.laya.report` for the integrated one.
- Laya's launcher uses the operating system `ssh` executable. Public users
  who have no second machine can leave Laya disabled or select local inference.

## Tests

```bash
python -m pytest tests/unit/test_laya_shadow.py -q
```

The tests use fake model predictions and do not require weights or a GPU.
The developer's actual Wonyoung ROCm checkpoint is **not executed by these
local tests**; after installing, verify the model live and the private report.

# Running the assistant harness tests

Run from the repository root with Python 3.12 or newer. Install the existing
development dependencies first; no model, GPU, credentials, or browser download
is required for the default suite.

```powershell
.venv/Scripts/python.exe -m pip install -e ".[dev,ui-test]"
.venv/Scripts/python.exe scripts/test_assistant_harness.py --coverage --checks
```

On Linux, substitute `.venv/bin/python`. Node 24 and the frontend dependencies
(`npm ci --prefix frontend`) are needed for `--checks`. Linux installations that
import the audio bindings may also need the system PortAudio library; tests do
not open audio devices.

The runner returns a nonzero exit code if any requested test or check fails.
It retains exact argument vectors, exit codes, elapsed times, JUnit results,
logs, and coverage in `.pytest-work/assistant-harness/final/`. Choose a fresh
`--output` directory for each run so evidence from different revisions is kept
separate. These local artifacts are ignored by Git. CI retains the same evidence
as a build artifact.

## Layers

```powershell
# Isolated logic, state transitions, and protocol regressions
.venv/Scripts/python.exe scripts/test_assistant_harness.py --layer unit --output .pytest-work/assistant-harness/unit

# Real internal components with controlled external transports
.venv/Scripts/python.exe scripts/test_assistant_harness.py --layer integration --output .pytest-work/assistant-harness/integration

# New cross-component harness contracts, including all registered commands
.venv/Scripts/python.exe scripts/test_assistant_harness.py --layer harness --output .pytest-work/assistant-harness/harness

# Actual CLI subprocess plus existing entry-point checks
.venv/Scripts/python.exe scripts/test_assistant_harness.py --layer smoke --output .pytest-work/assistant-harness/smoke

# Focus a run using ordinary pytest arguments after --
.venv/Scripts/python.exe scripts/test_assistant_harness.py --layer harness --output .pytest-work/assistant-harness/hermes -- -k hermes
```

These layers overlap deliberately. `all` (the default) discovers the whole
`tests/` tree once. Folder names in the older suite do not always identify a
test's isolation level: some `unit` tests launch disposable Python processes or
owned local HTTP services. Direct pytest invocation also installs the offline
guard through `tests/conftest.py`:

```powershell
.venv/Scripts/python.exe -m pytest tests/harness -o addopts= -q
```

## Offline boundaries

The default Python tests block external TCP/UDP and external DNS, and allow
loopback connections only to listeners registered by the test processes. A
cross-process locked journal lets disposable HTTP/MCP fixtures share their
owned ports without allowing access to the owner's existing localhost services.

Each test gets temporary default data/state roots. File and SQLite audit hooks
reject access to the repository's live `data/`, `state/`, `.env`, and known user
assistant directories. Credential APIs report an absent credential or reject
writes. Audio streams, playback, screenshots, and OS/hardware launchers are
blocked unless a test replaces the external boundary with its explicit fake.
Synthetic calendar, clipboard, screen-text, model, and Hermes fixtures exercise
the real internal adapters, routers, stores, and policies.

The guard is test infrastructure, **not an OS sandbox**. Python children that
inherit the test environment load it through `sitecustomize`; arbitrary native
binaries or children that discard that environment do not gain a firewall or
filesystem sandbox. The suite only launches reviewed, disposable fixture
processes. Installing dependencies is a separate network operation before tests.

`test_offline_guard.py` checks the network, production-storage, device, and child
process boundaries. Do not bypass these guards to make a failing test pass:
replace the actual external boundary and retain real internal behavior instead.

## Coverage and other checks

`--coverage` measures line and branch coverage of all `src/hanni` modules with
Coverage.py. There are no source omissions. Python subprocess statements are
not instrumented; assertions and process receipts still test their behavior.
The JSON report retains statement counts, branch counts, missing lines, and
missing branch arcs. A percentage is evidence about execution, not proof of
correctness or live integration compatibility. Missing Coverage.py is reported
explicitly; install the project's dev extra to obtain it.

`--checks` compiles Python source/tests, type-checks TypeScript, runs the frontend
Node tests (`*.test.ts` and `*.test.mjs`), builds the shipped frontend, builds a
wheel without build isolation, and checks its distribution contents. Python
linting is not configured by this campaign. The frontend build updates the
shipped files in `src/hanni/dashboard/static`; review those generated changes.

## Scope and interpretation

The [campaign report](report.md) records discovered capabilities, traceability,
failures, fixes, coverage, and skips. Controlled timing tests establish bounded
control behavior, not inference speed. Local/API model transport tests verify
the implemented OpenAI-compatible JSON/SSE contracts with fixtures, not every
provider's current API. Real GPU allocation, KV-cache behavior, microphone/wake
accuracy, audibility, Google authentication, external memory/MCP services, and
remote Hermes remain separate manual or live-service checks.

Command names come from `hanni.dashboard.commands.CATALOG`; the harness iterates
that registry and keeps a reviewed semantic case for each entry. A new entry
must receive valid fixture input and state assertions. Commands are
case-insensitive; the direct API requires the slash at position zero, while the
UI trims input. There is no general shell-style argument/alias parser. Reminder
time quoting and documented subcommand aliases are covered by their dedicated
contract tests. Never interpret text interpolation as permission to execute it.

Evaluation coverage v4 appends reviewed probes to the byte-preserved v3 corpus.
The migration manifest records hashes; v1-v3 are historical evidence and must
not be rewritten to make a new capability pass. Git preserves the v4 corpus
bytes through `.gitattributes`, including on Windows checkouts. The idempotent
extension script is `scripts/extend_harness_corpora.py`.

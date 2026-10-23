# Model data boundaries

HANNI's resident model receives a routed menu of at most eight MCP capabilities. The registry enforces permission levels at execution. `powershell.run` is never model-facing. The LLM benchmark replaces every capability result with synthetic data and never calls real handlers.

For local files, the MCP host blocks content and metadata requests aimed at recognized credential paths (`.env*`, OAuth/client-secret/token JSON, SSH/cloud credential directories, private-key suffixes and similar names). It resolves links before classifying paths. Filename search, exact locate and directory listing filter recognized sensitive paths from results; recursive content grep already filters them. Model-facing tool responses also pass through the existing value redactor. [Synthetic privacy tests](../tests/unit/test_mcp.py) cover content, filename and folder exposure, including a private directory.

This is a conservative known-pattern boundary, not a general classifier for arbitrary private material. An ordinary file with an innocuous name may still contain private data if the owner asks HANNI to read it; the redactor catches known token formats but cannot guarantee removal of every secret. `env.get` and `env.list` use secret-shaped variable-name filtering; startup command strings and other OS metadata deserve further review before claiming a complete privacy audit. Google API access remains an explicit connected integration and is absent from mock benchmark execution.

The dashboard binds to loopback and the configured model endpoint is restricted to loopback. The local Spotify tool uses the desktop client, not Spotify Web API. Google Calendar/Gmail calls require external Google access when invoked; `llama-server -hf` can fetch uncached model weights at startup. A cached local model path avoids that fetch. Local diagnostics, files, media, routing and synthetic evals do not need a Google connection.

Before promoting Tool Intelligence V1, audit all model-facing payload fields, especially startup command lines, environment values, archives, browser metadata and error text. Keep raw transcripts and credentials out of source exports and benchmark fixtures.

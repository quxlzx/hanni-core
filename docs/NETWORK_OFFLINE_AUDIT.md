# Network and offline audit

| Path | Destination | Offline behavior |
| --- | --- | --- |
| Model inference and health | Configured loopback llama.cpp endpoint | Works when the local server and weights are available. |
| Dashboard and browser chat | `127.0.0.1` only | Works locally; does not require a cloud account. |
| Voice STT/TTS | Local Windows and cached speech models | Works with installed/cached dependencies; missing models or voice packages must be reported. |
| System, file, app, and media tools | Local machine | Works without HANNI cloud access; Spotify playback still depends on the desktop client's own connectivity. |
| Google login, Calendar and Gmail | Google OAuth/API endpoints | Unavailable offline. HANNI should report auth or connectivity failure, not invent events or mail. |
| First model load with `-hf` | Model repository via llama.cpp | May download uncached weights; an explicitly configured local GGUF avoids this path. |
| Explicit network diagnostics | Requested host/service | Can make network requests only when the relevant capability is actually invoked. The LLM tool eval mocks these results. |

The static audit found no requirement to reach Google during local routing, diagnostics or synthetic benchmarks. It is not a packet-capture proof that every dependency stays offline. An end-to-end disconnected startup test remains before any release claim. Developer logs should identify optional external requests and failures without logging OAuth tokens, credentials, raw mail or private transcripts.

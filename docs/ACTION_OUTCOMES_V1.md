# Action outcome semantics

HANNI must distinguish an accepted request from a verified state change. The completion ledger tracks each requested clause using actual MCP results; it does not promote an unverified action to success.

| Capability | Current evidence | Safe response strength |
| --- | --- | --- |
| `app.open` | Windows launch request accepted; generic app-running state is not verified | “Launch request sent; I couldn't verify it opened.” |
| `spotify.launch` | Local Spotify process observed after launch | Spotify client is running; playback is still unverified. |
| `spotify.play_pause` | Local client window reports the playback state after the request | State reported by the client, with the window-title source disclosed. |
| `spotify.next` / `spotify.previous` | Media command sent and local window re-read | Report the observed track/state; do not infer that an unchanged title proves a skip. |
| `media.play_pause` / transport keys | Windows virtual key sent | Request sent; no player-specific playback verification. |
| `google_calendar.create` | Google API returns a created event | Calendar event created in the connected account. |

`play spotify` requires playback evidence; `open spotify` only requires the client launch. A generic `app.status`, `app.focus`, or `app.close_safe` capability is not currently registered. “Close Discord” must not be mapped to process termination as a substitute.

Tool errors already return concise structured codes such as permission denied, not found, timeout and invalid arguments through the existing capability facade. A complete error taxonomy with explicit transient/auth/dependency classes and tested recovery text remains open. The runtime completion ledger suppresses false action-success claims when the tool returns failure or only an accepted app-launch request. This does not guarantee that a 4B model phrases every read-only diagnosis correctly; the live eval and manual transcript review remain required.

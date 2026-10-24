---
name: strata-endpoint-diagnostics
description: Diagnose a configured Strata inference endpoint, model-not-found errors, and unhealthy or slow inference. Use actual configuration and receipts before changing a server.
metadata:
  hanni:
    triggers: [strata, endpoint, model not found, inference server]
---

# Strata endpoint diagnosis

1. Read the active model configuration and connection status. Record the endpoint, advertised model identifier, configured context and provider type. Never print API keys. Do not guess a host, model ID, service name or installation path from older notes.
2. With the configured connection, check `/health` (when supported) and `/v1/models`. A reachable server with a missing model ID is a configuration mismatch; a refused connection is a different failure. Record HTTP status, time and the advertised IDs. Local private endpoints require an authorized local terminal or configured inference adapter; public `web_fetch` intentionally blocks them.
3. Compare the configured API model identifier with the actual model listing. Inspect the current startup arguments and bounded server log excerpts when authorized. Check context support, GPU offload and Q8 key/value cache independently; RAM fallback is valid when no supported GPU is available.
4. Propose the smallest configuration correction supported by those observations. Keep the prior values for rollback. Check for active jobs before a restart and obtain any authorization required by the execution policy. If this is the endpoint serving the current agent, expect inference to be temporarily unavailable during loading.
5. After a change, repeat health and model-list checks, then send a small completion to the exact advertised model. Verify the response and cache/offload allocations from fresh receipts. Report unverified settings as unverified; wall-clock latency alone is not decode throughput.

If logs report a hipBLASLt tuning-table version mismatch, compare the file and runtime versions from the current log. Do not copy an old table or assume that an archived hardware-specific benchmark applies. Verify tuning acceptance and equivalent cache warmup before comparing performance.

After a successful correction, use `skill_save` with the current revision, the correction, and concrete verification evidence to retain a newly learned pitfall. Skill updates improve future instructions; they do not train model weights.

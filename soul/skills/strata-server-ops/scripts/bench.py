#!/usr/bin/env python3
"""Strata benchmark: 5 sequential runs, prints prefill/decode tok/s + draft
acceptance per run and an aggregate. Run with the API key sourced from
~/.hanni/.env. Compare only quiet batches (own traffic skews results)."""
import json, os, time, urllib.request

KEY = os.environ["HERMES_CUSTOM_OPENAI_COMPATIBLE_CUSTOM_OPENAI_API_KEY"]
URL = "http://<tailnet-ip>:8080/v1/chat/completions"
MODEL = "qwen3.8-flash-next-iq3_s"

base_para = ("The quick brown fox jumps over the lazy dog near the riverbank while "
 "birds circle overhead and the wind rustles through the tall grass. Engineers "
 "measure inference throughput in tokens per second, separating prompt processing "
 "from token generation, and account for speculative decoding acceptance rates. ")

results = []
for i in range(5):
    # vary prompt slightly per run so KV cache reuse doesn't fake the prefill number
    prompt = (f"Benchmark run {i+1}. " + base_para * 9 +
              "\nQuestion: What is 17 times 23? Answer with just the number.")
    body = {"model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150, "temperature": 0, "enable_thinking": False}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=240) as r:
        d = json.loads(r.read())
    wall = time.time() - t0
    t = d["timings"]; u = d["usage"]
    row = {"run": i + 1,
           "prompt_tokens": u["prompt_tokens"],
           "completion_tokens": u["completion_tokens"],
           "cached_tokens": u.get("prompt_tokens_details", {}).get("cached_tokens", 0),
           "prefill_tok_s": t["prompt_per_second"],
           "decode_tok_s": t["predicted_per_second"],
           "draft_accepted": f'{t.get("draft_n_accepted",0)}/{t.get("draft_n",0)}',
           "wall_s": round(wall, 2),
           "answer": (d["choices"][0]["message"].get("content") or "").strip()[:40]}
    results.append(row)
    print(json.dumps(row))
    if i < 4:
        time.sleep(8)  # let the single slot breathe

agg = {"runs": len(results),
       "avg_prefill_tok_s": round(sum(r["prefill_tok_s"] for r in results) / len(results), 1),
       "avg_decode_tok_s": round(sum(r["decode_tok_s"] for r in results) / len(results), 1),
       "avg_wall_s": round(sum(r["wall_s"] for r in results) / len(results), 2)}
print("AGG " + json.dumps(agg))

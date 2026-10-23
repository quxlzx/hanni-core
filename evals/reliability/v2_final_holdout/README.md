# Reliability V2 final holdout, published after evaluation

These exact sixty cases and their independent oracle were private throughout development. Original791bdab was evaluated before implementation; final741a776 was evaluated once after explicit final source freeze. No failure was used for tuning or rerunning the final candidate. They are published only after both actual configured-model and metadata runs completed, at the coordinator's request. **This set is now contaminated for future development: use a newly sequestered holdout.** Historical/public development corpora are not generalization evidence.

`manifest.json`, `final.jsonl`, `live-oracle.json` and both evaluator files retain their original bytes. Local `.gitattributes` disables text normalization for those immutable artifacts. Initial manifest SHA `b1ccb0aa512a95f418582d7bc7814f096af6788be7da7f13e3bbd686ae433d25` describes generated LF text; Windows `write_text` stored equivalent CRLF bytes, whose raw SHA is `84e492db6d9dcaa66023c100af6637f1b67dc47ecbd585384993b19d541784b9`. All sixty original fields are equal to the original baseline artifact. Both hashes are disclosed; no query/answer edit occurred. Oracle SHA is `378f369023c0af6f289123fdbdbb3189b5ac43b66e4f774bae4c6306f81b61e2`.

Evaluator SHA256: retrieval `83690af98845b58d35842dc67e84d6632ff795171efe82575a032c6839b6ce19`; live `ce48052a1a18458df26fb706830be963329f59c33e001449e7f942e97daebfda`. `settings.json` records model/runtime config fingerprints. These probes use the original controller/registry/model APIs and explicitly controlled read-only adapters; no arbitrary OS/provider writes execute. Dynamic metadata is synthetic; real SDK integration is separately tested. Model inference itself is actual configured cached Qwen3.5-4B, not scripted. Live semantic argument checking is limited to expected file-search terms. Lexical answer patterns have documented formatting/clock-scope limits; never relabel this as independently verified real user-task completion.

To reproduce research results, first prepare an original source archive in this bundle's ignored `original/` directory. This is an explicit future evaluation, not another current acceptance run:

```powershell
$bundle = Join-Path (Get-Location) 'evals/reliability/v2_final_holdout'
git archive --format=zip --output="$bundle/original.zip" 791bdab
Expand-Archive -LiteralPath "$bundle/original.zip" -DestinationPath "$bundle/original"
.venv\Scripts\python.exe "$bundle/retrieval_probe.py" "$bundle" "$bundle/original" baseline
.venv\Scripts\python.exe "$bundle/live_probe.py" "$bundle" "$bundle/original" baseline
# Use the frozen final741a776 source checkout as the second source argument.
.venv\Scripts\python.exe "$bundle/retrieval_probe.py" "$bundle" (Get-Location) final
.venv\Scripts\python.exe "$bundle/live_probe.py" "$bundle" (Get-Location) final
.venv\Scripts\python.exe scripts/reliability_review/audit_model_arguments.py --source "$bundle/original" --bundle "$bundle" --label baseline
.venv\Scripts\python.exe scripts/reliability_review/audit_model_arguments.py --source (Get-Location) --bundle "$bundle" --label final
.venv\Scripts\python.exe scripts/reliability_review/summarize_holdout.py --bundle "$bundle" --output data/hanni-reliability-v2-review/reproduced-summary.json
```

The unchanged live evaluator requires the same existing local cached GGUF path recorded in its source. It asserts that cached file exists and starts a dedicated loopback model server with explicit `model_file`; it never downloads an absent model. It stops only its owned model process and records external model PIDs before/after. A different machine/model/cache is a changed experimental condition, not a reproduction. Generated fixtures/results remain ignored. Authoritative current results are under `data/hanni-reliability-v2-review/final-language-model/` and `final-holdout-summary.json`, with independent conclusions in `docs/reliability-reviews/m5-final-evaluation.md`.

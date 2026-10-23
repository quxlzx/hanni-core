# Curated real-world failure corpus

**Status: dormant until Tool Intelligence V1 freezes.** There are no accepted
real interaction failures here yet. The owner's example phrases and synthetic
benchmark cases are not mislabeled as observed failures.

`curated.jsonl` is the only versionable *observed-failure* corpus file. It is empty now. Raw
transcripts, logs, screenshots, account details, and unreviewed notes belong in
the ignored local `inbox/` or a `*.local.jsonl` file and must not be promoted
automatically. HANNI does not capture interactions for this corpus and does not
train or fine-tune from it.

After the V1 freeze, add a case only after manual review: verify it was a real
HANNI interaction, remove personal data and secrets, state the observed failure
and expected domains, classify the failure stage, then add a stable case ID.
`case.schema.json` defines the record shape. Do not store hidden reasoning or
OAuth material. A real failure can become a development regression; it must
never be used to rewrite the locked Personal Holdout V1.

The **sanitized synthetic** voice regression set now lives at
`evals/routing/voice_routing_v1.jsonl` so source exports include it. It covers
generic media, follow-ups, and casual routing. It contains no raw audio,
transcripts, account identifiers, or observed-success claims. It is development
material, never a blind holdout. Private real-world JSONL files remain excluded.

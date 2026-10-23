# Independent outcome foundation cycle 1

**FAIL: 8 passed / 12 independent exposed checks.** Evidence: `data/hanni-v3-review/outcome-independent-cycle-1.xml`. Tests use a genuine original registry `file.read` against temporary fixture JSON and its original returned-data verification; acceptance logic is production `evaluate_step`. This evaluates the foundation, not a workflow engine or real model.

Reviewed verification source SHA-256 is `f0e3233fbcacd615199f8b9dd3e8722d62b3400d06f39691e90ff5dcb969479d`; independent test SHA is `7b4781de7d9c5985e45d0d399e927f901a6ba674e817330371c4e3f3a7ac001d`.

Passing cases preserve the narrow scope of cited observations/calculations. Actual fixture values 9/10 support 90%, with independent=false and the original returned-data scope retained. A false 95% report, overflowing sums/percentages, omitted requested input, retained credential JSON, unsupported prose appended to an otherwise correct quote, and artifact text derived from an unverified analysis cannot become VERIFIED. Quoting untrusted instructions is permitted only as quoted data; it grants no permission.

Four failing checks are retained before repair:

| Finding | Severity | Actual outcome |
| --- | --- | --- |
| Prerequisite verification is a JSON string | Medium robustness | Uncaught AttributeError instead of conservative UNVERIFIED |
| Prerequisite verification is a JSON list | Medium robustness | Same uncaught exception |
| Source projection says verified but underlying original result.ok is false | High evidence integrity | Analysis incorrectly becomes VERIFIED |
| Source projection says verified but underlying original result verification is UNVERIFIED | High evidence integrity | Analysis incorrectly becomes VERIFIED |

The inconsistent projection fixtures mutate an in-memory copy of a real read result after obtaining genuine original evidence. They demonstrate that the foundation trusts the outer projection without checking contradictory underlying evidence; they do not establish a public API exploit or a real unauthorized action. The model does not directly create these source projections. Persisted corruption, integration drift or future source assembly must still fail conservatively rather than upgrade contradictory evidence.

A source prerequisite should have bounded structured verification and a successful underlying result. Original tool sources must preserve their original evidence status; analysis predecessors have a distinct checked-report scope and cannot be treated as generic tool receipts. Failure handling must distinguish these source kinds without weakening the existing refusal/privacy oracles.

The twelve test outcomes must not be averaged into task completion or planning intelligence. No provider, SSH, node power, Windows application, model, voice or production assistant starts. Sealed planning cases remain untouched. Service multi-step/cancellation/crash/resource/ancestor-junction integration remains pending.

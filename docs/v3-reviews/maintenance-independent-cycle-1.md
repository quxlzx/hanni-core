# Independent retention and artifact cleanup review

**PASS: four independent filesystem/queue checks and seven root unit checks (11/11).** Evidence: `data/hanni-v3-review/maintenance-independent-cycle-1.xml`. This is a frozen-source maintenance-module review, not a running workflow-engine or global artifact-budget acceptance.

The independent tests use real files inside isolated temporary roots. They prove that exact expired workflow-ID cleanup preserves an active sibling's report; bounded partial cleanup retains its durable queue until completion; a mismatched queue identity cannot remove a folder; and a real Windows parent junction to an outside fixture directory is refused while the outside marker survives. Only the known temporary junction itself is removed after the test. No repository/user data or remote resource is touched.

The seven root tests additionally exercise age-based private context expiry, replay tombstones with immutable operation fingerprints, retention of active/uncertain work and live approval grants, bounded atomic deletion, durable cleanup across reopening, traversal/noncanonical queue rejection and partial cleanup. These tests are implementation-owned and reported separately from the four independent cases.

Source inspection confirms exact `GLOB artifact_gc:*` metadata selection, canonical workflow-ID-derived targets, link/reparse refusal, fixed absolute deletion boundaries, bounded unlink/rmdir operations and retained cleanup queue on error. Expired context deletion preserves operation identity/fingerprint, so an old request UUID cannot produce a second submission after retention.

| Reviewed file | SHA-256 |
| --- | --- |
| workflows/maintenance.py | `488f8bbf048fc547891ff2cbd724b0727639be4040a597e9ad9a1d971dfea37a` |
| independent maintenance tests | `cba894855651e8d6eb57c89b04e28fe791d0dca62bee4edcac63ca734bf3969a` |
| root maintenance tests | `8f29d9b3b8896c760bdd3c0458f38a3208c2ec8a220b6ed7205cd1490389f6e2` |

Runner integration, Safe Mode/foreground precedence, global shared artifact budget and the rule that private GET causes no housekeeping remain for the coherent engine-stage review. There is no model or application launch and no sealed planning-case evaluation in this review.

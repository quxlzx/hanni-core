# Independent callable binding repair review

**PASS: 3/3 unchanged exposed replacement checks.** Evidence: `data/hanni-v3-review/callable-binding-independent-cycle-1.xml`. Root's prior same-factory failure and checkpoint remain the pre-repair evidence; this report accepts the bounded binding repair, not a complete workflow engine.

The independent cases execute the original host and registry authority path with isolated local file handlers wrapped only to observe forbidden entry:

- A same-factory handler with a different captured closure is replaced before host validation. Old approval is denied before either replacement handler enters.
- The same method code is rebound to a different instance before host validation. Old approval is denied with zero handler entries.
- A real write request waits inside the original global mutation lane. While it is blocked, its captured definition is replaced. After the lane is released, the new definition is denied; no handler enters and no output file is written.

The replacement fixtures use `dataclasses.replace` on the previously registered definition, carrying its old binding field. The successful denial therefore also covers the registry's required overwrite of that carried token for a newly registered stateful callable. Registration assigns an opaque UUID for closures, bound instances and opaque callables; it does not serialize closure values, bound-object contents or credentials. The host's exact transient `ToolDefinition` object is additionally checked at audited dispatch after waiting for the original mutation lane. Default interactive requests carry neither workflow guard.

A separate two-process restart probe passed both identity expectations: the original plain `file.read` function retains the same fingerprint and empty binding across process/registry reconstruction; original closure-bound `todo.get` receives different binding/fingerprint in the second process. Evidence: `data/hanni-v3-review/callable-restart-probe.json`. Neither child executes a handler, provider call or model. These are two scoped probe assertions, reported separately from the three independent pytest cases. New process-bound approval must require fresh review; this does not claim that a complete service has implemented that recovery yet.

| Reviewed file | SHA-256 |
| --- | --- |
| tools/base.py | `dda3e8cfe967255a29f7490dd289668f0e8ed2e82153ffc36867fc7b0dbffe4a` |
| mcp/host.py | `ff0a72780affab34627909784dfc2bceb21d900121aa85fd88c9acb8839b1a87` |
| workflows/policy.py | `c44c1acf148049bf3afaf3ca76d22195d162d47d072e143c5341e33277a0ade8` |
| unchanged independent test file | `d88c1276d87649148e68ab02bcdad59f675c6691f51f45f8812eb79d4310958b` |

No production feature is authored by the verifier. No real application, node action, external provider, voice or model starts. The eighteen sealed planning cases remain unexecuted. Service restart authority, multi-step outcomes, engine races and final native review remain pending.

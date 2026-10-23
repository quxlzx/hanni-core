# Campaign 2 protocol

This campaign audits the current capability implementations and MCP Hub. The
starting revision is `e673ccc`. A separate common-instructions document could
not be located during Campaign 1; its recorded safety and evidence rules are
carried forward alongside the explicit Campaign 2 instructions.

The inventory is derived from the current default registry and a read-only
inspection of the owner's persisted MCP discovery. Counts are observations,
never an expected constant. Isolated MCP fixture tools are reported separately
from owner-enabled external tools. No owner MCP connection is enabled or changed.

Every discovered capability receives explicit outcomes for valid arguments,
invalid arguments, missing parameters, permission enforcement, unavailable
dependencies, output contracts, natural-language selection, and end-to-end
verification. A documented blocked or inapplicable outcome counts as documented
coverage, never as a successful test.

Implementation tests retain the original registered handler. Safe reads may
use live dependencies. Writes use disposable directories and isolated stores.
Unsafe GUI, process, service, playback, power and provider operations use
controlled leaf dependencies. Gate-only tests do not establish handler behavior.
Mock Google responses establish adapter behavior only, with no live Google API
claim. Owner processes, credentials, files, calendar, configuration and model
runtime remain protected. Only campaign-owned children may be stopped.

Output validation distinguishes successful payloads, unavailable/error payloads,
descriptive optional fields, and external MCP structured-content schemas.
Independent filesystem/store/provider readback supports end-to-end claims.
Natural-language retrieval and actual model inference are separate outcomes.
Inference preserves the existing admission guards and owner model defaults;
resource refusal is recorded, not bypassed.

Actual Codex workers implement platform and MCP audits. An independent Codex
verifier reproduces findings and checks dynamic coverage, evidence provenance,
permission boundaries and stale removal. The main agent integrates repairs,
tests and reports. Checkpoints preserve results after implementation and
verification cycles. Campaign 1's private holdout is not reused or opened.

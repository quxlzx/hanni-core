# Phase 3 setup and rollback

The two archives contain source candidates, not production deployment state. Retain each application's existing private configuration, `.env`, OAuth files, SSH credentials, model files, service units and authorized endpoint registry. Do not replace them with historical reports. HANNI owns task authorization; Control Center owns remote model lifecycle. No migration of lifecycle control is required. The shared module requires no additional dependency.

Review source diffs in an isolated checkout. HANNI source is under `hanni/`; Control Center source is under `control-center/`. The existing private Control Center URL/token and HANNI deployment bindings remain authoritative. Legacy API frames still work. Installing Control Center's new health snapshot code requires the existing deployment procedure and separately authorized protected-service restart; none was performed here. Do not create new network listeners or copy authentication secrets into either project.

HANNI production defaults remain unchanged. To test context in a controlled local checkout, enable the existing memory `context_enabled` option with its current byte budget and privacy controls. Leave LAYA disabled. To test routing, use the existing owner-confirmed Model Routing UI/API to choose `resident_first` or opt into `measured_work`; these are runtime policies, not newly supported YAML enum values. Record the prior policy before changing it. Existing remote deployment is synthetic-only, so these policies cannot send owner memory/projects/conversation remotely. Capability proofs, measured usable context, sample minimums and explicit privacy authorization must be supplied through the original processes before eligible remote work. Never bypass admission to make an endpoint appear usable.

From the HANNI repository with its existing environment:

```powershell
powershell -NoProfile -File scripts/check_phase3.ps1
powershell -NoProfile -File scripts/check_phase1.ps1
powershell -NoProfile -File scripts/check_phase2.ps1
cd frontend
npm run check
npm run build
```

The supplied receipts can be aggregated without inference: unpack `phase3_evidence/` into `data/phase3/`, then run `.venv\Scripts\python.exe scripts/phase3_results.py`. Reproduction of live checks requires the same already-running authorized endpoints and private registry; these commands make real bounded inference requests, but do not start models or execute tools:

```powershell
.venv\Scripts\python.exe scripts/phase3_model_eval.py --output data/phase3/reproduction-models.json
.venv\Scripts\python.exe scripts/phase3_cancel_eval.py --output data/phase3/reproduction-cancel.json
.venv\Scripts\python.exe scripts/phase3_integrated_eval.py --cases evals/phase3/memory-fresh.json --output data/phase3/reproduction-memory.json
```

Keep original results intact. Repeated runs are reproductions, not a fresh held-out cohort. The integrated harness uses an isolated actual memory store and read-only fixture file, with calendar credentials absent; it does not validate the owner's live calendar. The cancellation check closes only the SSH helper it owns; upstream cancellation is best effort.

Control Center offline validation requires its existing Python test requirements plus FastAPI/Starlette:

```powershell
python -m pytest tests/test_endpoint_contract.py tests/test_failure_cases.py -o addopts= -q
```

The evaluation environment used isolated test dependencies, not production dependency changes. See each project's original setup instructions for its actual runtime requirements.

Rollback routing through the same confirmed UI/API to the recorded previous policy; disable optional memory context if enabled for evaluation. For source rollback compare the included HANNI source baseline and manifests and restore only the Phase 3 edits in an isolated checkout, preserving unrelated changes. Control Center's added module/test and snapshot wrapper can be reverted to the supplied original source; legacy HANNI compatibility is maintained. Use your normal authorized deployment/rollback process if either candidate is later deployed; no service restart commands are run by these instructions. Rollback does not delete owner memory or revoke existing private permissions.

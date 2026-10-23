# Between-pass model admission: FAIL

The public independent actual-Service reproduction fails **0/1**. A valid scripted outline response raises the original InteractionState responding flag before returning. While that original state remains response_in_progress=True, the Service starts the next binding inference. Actual inference-call count is two; the conservative oracle requires one until fresh admission permits more work. No original file handler entered, and the goal reached awaiting_plan_approval.

This tests fresh admission before a later model call, not cancellation of the first already active synchronous call. Actual Service, planner, original host/registry and InteractionState are used. Only model reply generation is scripted; no real model, GUI, production assistant, provider or remote operation starts.

Preserved evidence: `data/hanni-v3-review/m3-planning-admission-independent-cycle-1.xml` and `m3-between-model-pass-admission-cycle-1.json`; independent test `tests/integration/test_workflow_planning_admission_verifier.py`. Service SHA at this failure is `6d38c295d8ff3e9f91c3ecf2c6deb47cfbb47d4fb6548a31be5c124520231f3f`. Source is not edited by the verifier. Root's other narrowly scoped callable/date repairs are separate from this unchanged Service scheduling boundary. The sealed eighteen planning cases are untouched.

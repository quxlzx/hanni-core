import {
  workflowLabel,
  type CollaborationVerification,
  type WorkflowStep,
} from "./workflow_types";

function duration(milliseconds: number | null | undefined) {
  if (
    typeof milliseconds !== "number" ||
    !Number.isFinite(milliseconds) ||
    milliseconds < 0
  )
    return "Not measured";
  return milliseconds < 1000
    ? `${Math.round(milliseconds)} ms`
    : `${(milliseconds / 1000).toFixed(1)} s`;
}

function Verification({
  evidence,
}: {
  evidence: CollaborationVerification | null;
}) {
  return (
    <span className="collaboration-verification">
      {evidence ? workflowLabel(evidence.status) : "Not verified"}
      {evidence?.scope && <small>{evidence.scope}</small>}
    </span>
  );
}

export function WorkflowCollaborationView({
  steps,
}: {
  steps: WorkflowStep[];
}) {
  const analyses = steps.filter((step) => step.kind === "analysis");
  if (!analyses.length) return null;
  const recorded = analyses.filter((step) => step.collaboration);
  return (
    <section
      className="workflow-collaboration"
      aria-label="Model collaboration"
    >
      <div className="section-title">
        <h2>Model collaboration</h2>
        <span>
          {recorded.length
            ? `${recorded.length} recorded ${recorded.length === 1 ? "analysis" : "analyses"}`
            : "No collaboration receipts"}
        </span>
      </div>
      {!recorded.length ? (
        <p className="collaboration-empty">
          This workflow has no recorded model collaboration. Analysis follows
          its saved model policy.
        </p>
      ) : (
        recorded.map((step) => {
          const run = step.collaboration!;
          return (
            <div
              className="collaboration-run"
              key={step.step_id}
              data-collaboration-step={step.step_id}
            >
              <div className="collaboration-heading">
                <strong>{step.description}</strong>
                <span>
                  {workflowLabel(run.effective_pattern)} ·{" "}
                  {workflowLabel(run.state)}
                </span>
              </div>
              <p className="collaboration-reason">{run.reason}</p>
              {(run.input_sha256 || run.context_refs?.length) && (
                <details className="collaboration-sources">
                  <summary>Input and source receipts</summary>
                  {run.input_sha256 && (
                    <p className="mono">Input SHA-256: {run.input_sha256}</p>
                  )}
                  {run.context_refs?.map((source) => (
                    <p key={source.step_id}>
                      {steps.find((item) => item.step_id === source.step_id)
                        ?.description || source.step_id}{" "}
                      · {workflowLabel(source.verification_status)}
                      <small className="mono">
                        {source.step_id} · {source.result_sha256}
                      </small>
                    </p>
                  ))}
                </details>
              )}
              <div
                className="collaboration-participant-heading"
                aria-hidden="true"
              >
                <span>Model / assignment</span>
                <span>State / evidence</span>
                <span>Inference</span>
                <span>Returned output</span>
              </div>
              {run.participants.length ? (
                run.participants.map((participant) => (
                  <div
                    className="collaboration-participant"
                    key={participant.participant_id}
                    data-participant-id={participant.participant_id}
                  >
                    <span>
                      <strong>
                        {participant.model_id || participant.endpoint_id}
                      </strong>
                      <small>{participant.assigned_task}</small>
                      <small className="mono">{participant.endpoint_id}</small>
                    </span>
                    <span>
                      {workflowLabel(participant.state)}
                      <Verification evidence={participant.verification} />
                    </span>
                    <span>
                      {duration(participant.latency_ms)}
                      <small>
                        {participant.tokens?.completion_tokens == null
                          ? "Tokens not measured"
                          : `${participant.tokens.completion_tokens} generated tokens`}
                      </small>
                    </span>
                    <span className="collaboration-output">
                      {participant.error ? (
                        <span className="collaboration-error">
                          {participant.error}
                        </span>
                      ) : (
                        participant.output_summary || "No output recorded"
                      )}
                      {participant.output != null && (
                        <details>
                          <summary>Full output and receipt</summary>
                          <pre>{participant.output}</pre>
                          <p className="mono">
                            Model identity: {participant.identity}
                          </p>
                          {participant.verification?.checks && (
                            <pre>
                              {JSON.stringify(
                                participant.verification.checks,
                                null,
                                2,
                              )}
                            </pre>
                          )}
                        </details>
                      )}
                    </span>
                  </div>
                ))
              ) : (
                <p className="collaboration-empty">
                  No participant has been admitted.
                </p>
              )}
              {run.conflicts.length > 0 && (
                <div className="collaboration-conflicts" role="status">
                  <strong>
                    {run.conflicts.length} recorded{" "}
                    {run.conflicts.length === 1
                      ? "disagreement"
                      : "disagreements"}
                  </strong>
                  {run.conflicts.map((conflict, index) => (
                    <p key={index}>
                      {workflowLabel(conflict.kind)} · {conflict.resolution}
                      <small>{conflict.participant_ids.join(" · ")}</small>
                    </p>
                  ))}
                </div>
              )}
              <div className="collaboration-outcome">
                <span>
                  <strong>Final evidence</strong>
                  <Verification evidence={run.final_verification} />
                </span>
                <span>
                  Elapsed: {duration(run.total_latency_ms)}
                  <small>
                    {run.generated_tokens == null
                      ? "Total tokens not measured"
                      : `${run.generated_tokens} total generated tokens`}
                  </small>
                </span>
                {run.selected_endpoint_id && (
                  <span>
                    Selected result
                    <small className="mono">{run.selected_endpoint_id}</small>
                  </span>
                )}
              </div>
            </div>
          );
        })
      )}
    </section>
  );
}

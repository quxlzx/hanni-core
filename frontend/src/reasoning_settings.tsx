import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { write } from "./api";
import { usePrivateResource } from "./feature_types";
import "./output_settings.css";

type ReasoningData = {
  available: boolean;
  reason?: string;
  ready?: boolean;
  model_id?: string;
  effort_levels?: string[];
  can_disable?: boolean;
  budget_supported?: boolean;
  effort?: string | null;
  budget?: number | null;
  effective_effort?: string | null;
  effective_budget?: number | null;
  max_budget?: number;
  output_limit?: number;
  customized?: boolean;
};
const effortLabel = (value?: string | null) => value === "none" ? "Off" : value ? value[0].toUpperCase() + value.slice(1) : "Model default";

export function ReasoningSettings({ token, disabled = false, showHeading = true }: { token: string; disabled?: boolean; showHeading?: boolean }) {
  const resource = usePrivateResource<ReasoningData>("/api/model-reasoning", token, 5000);
  const data = resource.data;
  const [effort, setEffort] = useState("default");
  const [mode, setMode] = useState("default"), [budget, setBudget] = useState("512");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const loaded = useRef<string | undefined>(undefined), dirty = useRef(false), lock = useRef(false);
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const id = useId();
  const maximum = data?.max_budget ?? 0;
  const valid = effort === "none" || !data?.budget_supported || mode !== "custom" || (/^\d+$/.test(budget) && Number.isSafeInteger(Number(budget)) && Number(budget) <= maximum);
  const blocked = disabled || busy || !token || !data?.available || Boolean(resource.error);
  const editable = !blocked && data?.ready;
  const levels = data?.effort_levels || [];
  const canChooseEffort = Boolean(data?.can_disable || levels.length);

  function initialize(next: ReasoningData) {
    setEffort(next.effort || "default");
    setMode(next.budget === -1 ? "uncapped" : next.budget != null ? "custom" : "default");
    setBudget(String(next.budget != null && next.budget >= 0 ? next.budget : Math.min(512, next.max_budget ?? 512)));
  }

  useEffect(() => {
    if (!data?.available) return;
    if (loaded.current !== data.model_id) {
      loaded.current = data.model_id; dirty.current = false;
      setError(""); setNotice("");
    }
    if (!dirty.current) initialize(data);
  }, [data]);

  function edit(action: () => void) {
    dirty.current = true; setError(""); setNotice(""); action();
  }

  async function save(reset = false) {
    if (blocked || lock.current || (!reset && (!editable || !valid))) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    const values = {
      model_id: data!.model_id,
      effort: reset || effort === "default" ? null : effort,
      budget: reset || effort === "none" || !data?.budget_supported || mode === "default" ? null : mode === "uncapped" ? -1 : Number(budget),
    };
    const signature = JSON.stringify(values);
    const requestId = pending.current?.signature === signature ? pending.current.id : crypto.randomUUID();
    pending.current = { signature, id: requestId };
    try {
      const saved = await write<ReasoningData>("/api/model-reasoning", token, { ...values, id: requestId });
      dirty.current = false; pending.current = null;
      resource.setData(saved); initialize(saved);
      setNotice(reset ? "Model reasoning defaults restored for new responses." : "Reasoning settings saved for this model. New responses use these settings; work already running keeps its current settings.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reasoning settings could not be saved. Retry to confirm them.");
    } finally {
      lock.current = false; setBusy(false); resource.refresh();
    }
  }

  function submit(event: FormEvent) { event.preventDefault(); void save(); }
  return <div className="output-settings reasoning-settings">
    {showHeading && <h3>Reasoning</h3>}
    <p className="output-description">Adjust the model's reasoning before it answers. Available controls depend on the connected model and server.</p>
    {resource.error && <p className="output-error" role="status">Could not load reasoning settings. {resource.error}</p>}
    {!data && !resource.error && <p role="status">Checking reasoning support…</p>}
    {data && !data.available && <p role="status">{data.reason || "Reasoning settings are unavailable in this session."}</p>}
    {data?.available && <>
      {!data.ready && <p className="output-error" role="status">{data.reason || "Connect the active model to change reasoning settings."}</p>}
      <p className="output-current">Current effort: <strong>{effortLabel(data.effective_effort)}</strong>{data.budget_supported && <span>Reasoning budget: {data.effective_budget === -1 ? "No separate cap" : data.effective_budget != null ? `${data.effective_budget.toLocaleString()} tokens` : "Server default"}</span>}</p>
      <form onSubmit={submit}>
        <fieldset disabled={!editable}>
          <legend className="sr-only">Reasoning settings for the active model</legend>
          <div className="output-fields">
            {canChooseEffort && <label htmlFor={`${id}-effort`}>Reasoning effort<select id={`${id}-effort`} value={effort} onChange={event => edit(() => setEffort(event.target.value))}><option value="default">Model default</option>{data.can_disable && <option value="none">Off</option>}{levels.map(level => <option key={level} value={level}>{effortLabel(level)}</option>)}</select></label>}
            {data.budget_supported && <label htmlFor={`${id}-mode`}>Reasoning token limit<select id={`${id}-mode`} disabled={effort === "none"} value={mode} onChange={event => edit(() => setMode(event.target.value))}><option value="default">Model default</option><option value="custom">Custom budget</option><option value="uncapped">No separate cap</option></select></label>}
            {data.budget_supported && mode === "custom" && effort !== "none" && <label htmlFor={`${id}-tokens`}>Maximum reasoning tokens<input id={`${id}-tokens`} type="number" inputMode="numeric" min={0} max={maximum} step={1} required value={budget} aria-describedby={`${id}-help`} onChange={event => edit(() => setBudget(event.target.value))} /></label>}
          </div>
          {!levels.length && data.budget_supported && <p className="output-help">This model does not advertise Low, Medium or High effort levels. You can still control its reasoning-token budget.</p>}
          {!canChooseEffort && !data.budget_supported && <p className="output-help">This connection does not advertise adjustable reasoning. Choose a supported model to enable these controls.</p>}
          <p id={`${id}-help`} className="output-help">{data.budget_supported ? `Custom budget: 0–${maximum.toLocaleString()} tokens; 0 ends reasoning immediately. Reasoning shares the ${data.output_limit?.toLocaleString()}-token output limit. Increase Maximum output tokens for longer reasoning and answers. No separate cap still respects the overall output limit.` : "This API connection manages reasoning-token budgets. Hanni sends only the effort levels it advertises."}</p>
          <div className="output-actions"><button type="submit" disabled={!editable || !valid || (!canChooseEffort && !data.budget_supported)}>{busy ? "Saving…" : "Save reasoning settings"}</button></div>
        </fieldset>
        <div className="output-actions reasoning-reset"><button type="button" disabled={blocked || !data.customized} onClick={() => void save(true)}>Use reasoning defaults</button></div>
      </form>
    </>}
    {error && <p className="output-error" role="alert">{error}</p>}
    {notice && <p className="output-notice" role="status">{notice}</p>}
  </div>;
}

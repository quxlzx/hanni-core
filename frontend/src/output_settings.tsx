import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { write } from "./api";
import { usePrivateResource } from "./feature_types";
import "./output_settings.css";

type OutputData = {
  available: boolean;
  reason?: string;
  model_id?: string;
  model?: string;
  max_tokens?: number;
  default_max_tokens?: number;
  minimum?: number;
  maximum?: number;
  customized?: boolean;
};
const presets = [1024, 2048, 4096, 8192, 16384, 32768, 65536];

export function OutputSettings({ token, disabled = false, showHeading = true }: { token: string; disabled?: boolean; showHeading?: boolean }) {
  const resource = usePrivateResource<OutputData>("/api/model-output", token, 3000);
  const data = resource.data;
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const loaded = useRef<string | undefined>(undefined), dirty = useRef(false), lock = useRef(false);
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const id = useId();
  const maximum = data?.maximum || 65536;
  const numeric = Number(value);
  const valid = /^\d+$/.test(value) && Number.isSafeInteger(numeric) && numeric >= 1 && numeric <= maximum;
  const blocked = disabled || busy || !token || !data?.available || Boolean(resource.error);

  useEffect(() => {
    if (!data?.available) return;
    if (loaded.current !== data.model_id) {
      loaded.current = data.model_id;
      dirty.current = false;
      setError(""); setNotice("");
    }
    if (!dirty.current) setValue(String(data.max_tokens));
  }, [data]);

  function edit(next: string) {
    dirty.current = true;
    setValue(next); setError(""); setNotice("");
  }

  async function save(reset = false) {
    if (blocked || lock.current || (!reset && !valid)) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    const values = { model_id: data!.model_id, max_tokens: reset ? null : numeric };
    const signature = JSON.stringify(values);
    const requestId = pending.current?.signature === signature ? pending.current.id : crypto.randomUUID();
    pending.current = { signature, id: requestId };
    try {
      const saved = await write<OutputData>("/api/model-output", token, { ...values, id: requestId });
      dirty.current = false; pending.current = null;
      resource.setData(saved); setValue(String(saved.max_tokens));
      setNotice(`Saved: up to ${saved.max_tokens?.toLocaleString()} output tokens per model response. Applies to new responses; work already running keeps its current limit.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The output limit could not be saved. Retry to confirm it.");
    } finally {
      lock.current = false; setBusy(false); resource.refresh();
    }
  }

  function submit(event: FormEvent) { event.preventDefault(); void save(); }
  return <div className="output-settings">
    {showHeading && <h3>Response length</h3>}
    <p className="output-description">Set an upper limit for each model response. The model can finish sooner, and tool workflows can use several responses.</p>
    {resource.error && <p className="output-error" role="status">Could not load output settings. {resource.error}</p>}
    {!data && !resource.error && <p role="status">Loading output settings…</p>}
    {data && !data.available && <p role="status">{data.reason || "Output settings are unavailable in this session."}</p>}
    {data?.available && <>
      <p className="output-current">Current limit: <strong>{data.max_tokens?.toLocaleString()} tokens</strong><span>{data.customized ? "Saved for this model" : "Model default"}</span></p>
      <form onSubmit={submit}>
        <fieldset disabled={blocked}>
          <legend className="sr-only">Output limit for the active model</legend>
          <div className="output-fields">
            <label htmlFor={`${id}-preset`}>Preset<select id={`${id}-preset`} value={presets.includes(numeric) ? numeric : "custom"} onChange={event => { if (event.target.value !== "custom") edit(event.target.value); }}><option value="custom">Custom limit</option>{presets.filter(limit => limit <= maximum).map(limit => <option key={limit} value={limit}>{limit.toLocaleString()} tokens</option>)}</select></label>
            <label htmlFor={`${id}-tokens`}>Maximum output tokens<input id={`${id}-tokens`} type="number" inputMode="numeric" min={data.minimum || 1} max={maximum} step={1} required value={value} aria-describedby={`${id}-help`} onChange={event => edit(event.target.value)} /></label>
          </div>
          <p id={`${id}-help`} className="output-help">1–{maximum.toLocaleString()} tokens for the active model. Space is reserved for input within the context window. Provider limits still apply; reasoning may count toward this cap.</p>
          <div className="output-actions"><button type="submit" disabled={blocked || !valid || numeric === data.max_tokens}>{busy ? "Saving…" : "Save output limit"}</button><button type="button" disabled={blocked || !data.customized} onClick={() => void save(true)}>Use model default</button></div>
        </fieldset>
      </form>
    </>}
    {error && <p className="output-error" role="alert">{error}</p>}
    {notice && <p className="output-notice" role="status">{notice}</p>}
  </div>;
}
